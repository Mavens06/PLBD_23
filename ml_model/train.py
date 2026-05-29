"""
train.py
--------
Pipeline d'entraînement pour la recommandation de culture Agribotics.

Modèles candidats :
  1. Random Forest Classifier
  2. Support Vector Classifier (RBF)
  3. Gradient Boosting Classifier
  4. Logistic Regression

Évaluation :
  • Validation croisée stratifiée (StratifiedKFold, k=5) sur le train set
    avec F1-macro comme score primaire (équilibre entre classes).
  • Évaluation finale sur le test set : Accuracy, Précision, Rappel,
    F1-macro et F1-pondéré.

Sélection : F1-macro le plus élevé sur le test set (en cas d'égalité,
F1-pondéré puis accuracy).

Artefacts :
  ml_model/data/final_dataset.csv  — dataset synthétique
  ml_model/scaler.pkl              — StandardScaler ajusté
  ml_model/best_model.pkl          — meilleur modèle sérialisé (pickle)

Utilisation :
    python ml_model/train.py
"""

from __future__ import annotations

import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, f1_score,
                             precision_score, recall_score)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.svm import SVC


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from preprocess import preprocess          # noqa: E402
from data_preparation import create_final_dataset   # noqa: E402

CSV_PATH = SCRIPT_DIR / "data" / "final_dataset.csv"
SCALER_PATH = SCRIPT_DIR / "scaler.pkl"
BEST_MODEL_PATH = SCRIPT_DIR / "best_model.pkl"

RANDOM_STATE = 42
CV_FOLDS = 5


def build_models() -> dict:
    return {
        "Random Forest": RandomForestClassifier(
            n_estimators=300, max_depth=None, min_samples_split=2,
            n_jobs=-1, random_state=RANDOM_STATE,
        ),
        "SVC (RBF)": SVC(
            kernel="rbf", C=10, gamma="scale", probability=True,
            random_state=RANDOM_STATE,
        ),
        "Gradient Boosting": GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.1, max_depth=4,
            random_state=RANDOM_STATE,
        ),
        "Logistic Regression": LogisticRegression(
            max_iter=2000, solver="lbfgs",
            random_state=RANDOM_STATE,
        ),
    }


def top_k_accuracy(model, X_test, y_test, k: int = 3) -> float:
    """Proportion des cas où la vraie culture est dans les k meilleures
    probabilités. C'est la métrique alignée sur le produit : l'API expose
    un top-3, pas une culture unique. Pertinente car les plages agronomiques
    se chevauchent fortement (la prédiction d'une culture unique est mal posée).
    """
    if not hasattr(model, "predict_proba"):
        return float("nan")
    proba = model.predict_proba(X_test)
    classes = np.asarray(model.classes_)
    top_k = classes[np.argsort(-proba, axis=1)[:, :k]]
    hits = [yt in row for yt, row in zip(np.asarray(y_test), top_k)]
    return float(np.mean(hits))


def evaluate_test(model, X_test, y_test) -> dict:
    y_pred = model.predict(X_test)
    return {
        "accuracy":     round(accuracy_score(y_test, y_pred), 4),
        "precision_w":  round(precision_score(y_test, y_pred, average="weighted", zero_division=0), 4),
        "recall_w":     round(recall_score(y_test, y_pred,    average="weighted", zero_division=0), 4),
        "f1_weighted":  round(f1_score(y_test, y_pred,        average="weighted", zero_division=0), 4),
        "f1_macro":     round(f1_score(y_test, y_pred,        average="macro",    zero_division=0), 4),
        "top3_acc":     round(top_k_accuracy(model, X_test, y_test, k=3), 4),
    }


def cross_validate_f1_macro(model, X_train, y_train) -> tuple[float, float]:
    skf = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    scores = cross_val_score(model, X_train, y_train, cv=skf,
                             scoring="f1_macro", n_jobs=-1)
    return float(scores.mean()), float(scores.std())


def train_and_select(regenerate: bool = True) -> tuple[str, object, pd.DataFrame]:
    if regenerate:
        print("=" * 70)
        print("  ÉTAPE 0 : (Re)génération du dataset synthétique")
        print("=" * 70)
        _, report = create_final_dataset(output_path=CSV_PATH)
        print(f"  {report['rows']} lignes · {report['classes']} classes · "
              f"features {report['features']} → {report['output']}")

    print("=" * 70)
    print("  ÉTAPE 1 : Prétraitement (load + scale + split stratifié)")
    print("=" * 70)
    X_train, X_test, y_train, y_test, _ = preprocess()

    print("\n" + "=" * 70)
    print(f"  ÉTAPE 2 : Entraînement + CV {CV_FOLDS} folds + test final")
    print("=" * 70)

    results = {}
    trained = {}

    for name, model in build_models().items():
        print(f"\n  → {name}")
        t0 = time.time()
        cv_mean, cv_std = cross_validate_f1_macro(model, X_train, y_train)
        cv_time = time.time() - t0
        print(f"     CV F1-macro : {cv_mean:.4f} ± {cv_std:.4f}  ({cv_time:.1f}s, {CV_FOLDS} folds)")

        t1 = time.time()
        model.fit(X_train, y_train)
        fit_time = time.time() - t1
        m = evaluate_test(model, X_test, y_test)
        m["cv_f1_macro_mean"] = round(cv_mean, 4)
        m["cv_f1_macro_std"] = round(cv_std, 4)
        m["fit_time_s"] = round(fit_time, 2)
        results[name] = m
        trained[name] = model
        print(f"     TEST  Acc={m['accuracy']:.4f}  F1-macro={m['f1_macro']:.4f}  "
              f"F1-w={m['f1_weighted']:.4f}  Top-3={m['top3_acc']:.4f}")

    print("\n" + "=" * 70)
    print("  ÉTAPE 3 : Comparaison")
    print("=" * 70)
    cols = ["accuracy", "f1_macro", "f1_weighted", "top3_acc",
            "cv_f1_macro_mean", "cv_f1_macro_std", "fit_time_s"]
    results_df = pd.DataFrame(results).T[cols].sort_values(
        ["f1_macro", "f1_weighted", "accuracy"], ascending=False,
    )
    results_df.index.name = "Modèle"
    print(results_df.to_string())

    best_name = results_df.index[0]
    best_model = trained[best_name]
    best = results[best_name]

    print("\n" + "=" * 70)
    print("  ÉTAPE 4 : Meilleur modèle")
    print("=" * 70)
    print(f"  ✅ {best_name}")
    print(f"     Top-3 acc   : {best['top3_acc']:.4f}   ← métrique produit (API top-3)")
    print(f"     F1-macro    : {best['f1_macro']:.4f}")
    print(f"     F1-pondéré  : {best['f1_weighted']:.4f}")
    print(f"     Accuracy    : {best['accuracy']:.4f}   (top-1, plafonnée par le chevauchement des plages)")
    print(f"     CV F1-macro : {best['cv_f1_macro_mean']:.4f} ± {best['cv_f1_macro_std']:.4f}")

    # Rapport détaillé par classe
    y_pred = best_model.predict(X_test)
    print("\n  Classification report (par culture) :")
    print(classification_report(y_test, y_pred, zero_division=0))

    with open(BEST_MODEL_PATH, "wb") as f:
        pickle.dump(best_model, f)
    print(f"  💾 Modèle sauvegardé → {BEST_MODEL_PATH}")
    print(f"  💾 Scaler sauvegardé → {SCALER_PATH}")

    return best_name, best_model, results_df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Entraînement des modèles Agribotics")
    parser.add_argument("--no-regenerate", action="store_true",
                        help="Ne pas régénérer le dataset, réutiliser data/final_dataset.csv existant")
    args = parser.parse_args()
    train_and_select(regenerate=not args.no_regenerate)
