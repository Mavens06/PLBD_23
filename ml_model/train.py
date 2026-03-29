"""
train.py
--------
Pipeline d'entraînement pour la recommandation de cultures agricoles marocaines.

Modèles entraînés :
  1. Random Forest Classifier
  2. Support Vector Classifier (SVC)
  3. Gradient Boosting Classifier
  4. Logistic Regression

Métriques d'évaluation : Accuracy, Précision, Rappel, F1-Score (weighted).
Critère de sélection : F1-Score (pondéré) — adapté aux classes multiples.

Artefacts produits :
  ml_model/moroccan_crop_data.csv  — dataset synthétique marocain
  ml_model/scaler.pkl              — scaler StandardScaler ajusté
  ml_model/best_model.pkl          — meilleur modèle sérialisé

Utilisation :
    python ml_model/train.py
"""

import os
import sys
import pickle
import time
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

# ── Import local des modules du pipeline ──────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from data_loader import generate_dataset
from preprocess import preprocess

# ── Chemins ────────────────────────────────────────────────────────────────────
CSV_PATH        = os.path.join(SCRIPT_DIR, "moroccan_crop_data.csv")
SCALER_PATH     = os.path.join(SCRIPT_DIR, "scaler.pkl")
BEST_MODEL_PATH = os.path.join(SCRIPT_DIR, "best_model.pkl")

RANDOM_STATE = 42

# ── Définition des modèles candidats ──────────────────────────────────────────
MODELS = {
    "Random Forest": RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        min_samples_split=2,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    ),
    "SVC": SVC(
        kernel="rbf",
        C=10,
        gamma="scale",
        probability=True,
        random_state=RANDOM_STATE,
    ),
    "Gradient Boosting": GradientBoostingClassifier(
        n_estimators=150,
        learning_rate=0.1,
        max_depth=5,
        random_state=RANDOM_STATE,
    ),
    "Logistic Regression": LogisticRegression(
        max_iter=1000,
        solver="lbfgs",
        random_state=RANDOM_STATE,
    ),
}


def evaluate_model(model, X_test, y_test) -> dict:
    """Calcule les métriques clés sur l'ensemble de test."""
    y_pred = model.predict(X_test)
    return {
        "accuracy":  round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, average="weighted", zero_division=0), 4),
        "recall":    round(recall_score(y_test, y_pred,    average="weighted", zero_division=0), 4),
        "f1_score":  round(f1_score(y_test, y_pred,        average="weighted", zero_division=0), 4),
    }


def train_and_select():
    """
    Orchestre l'ensemble du pipeline :
      1. Génère (ou recharge) le dataset marocain.
      2. Prétraite les données.
      3. Entraîne tous les modèles.
      4. Compare leurs métriques.
      5. Sélectionne et sauvegarde le meilleur modèle.
    """
    # ── Étape 1 : Données ─────────────────────────────────────────────────────
    if not os.path.exists(CSV_PATH):
        print("=" * 60)
        print("  ÉTAPE 1 : Génération du dataset marocain")
        print("=" * 60)
        generate_dataset(output_path=CSV_PATH)
    else:
        print(f"[train] Dataset existant chargé : {CSV_PATH}")

    # ── Étape 2 : Prétraitement ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  ÉTAPE 2 : Prétraitement des données")
    print("=" * 60)
    X_train, X_test, y_train, y_test, _ = preprocess(CSV_PATH, SCALER_PATH)  # scaler déjà sauvegardé sur disque

    # ── Étape 3 : Entraînement ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  ÉTAPE 3 : Entraînement des modèles")
    print("=" * 60)

    results = {}
    trained_models = {}

    for name, model in MODELS.items():
        print(f"\n  → Entraînement : {name} ...")
        t0 = time.time()
        model.fit(X_train, y_train)
        elapsed = time.time() - t0
        metrics = evaluate_model(model, X_test, y_test)
        results[name] = metrics
        trained_models[name] = model
        print(
            f"     Durée : {elapsed:.2f}s | "
            f"Accuracy={metrics['accuracy']:.4f} | "
            f"Précision={metrics['precision']:.4f} | "
            f"Rappel={metrics['recall']:.4f} | "
            f"F1={metrics['f1_score']:.4f}"
        )

    # ── Étape 4 : Comparaison ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  ÉTAPE 4 : Comparaison des modèles")
    print("=" * 60)

    results_df = pd.DataFrame(results).T.sort_values("f1_score", ascending=False)
    results_df.index.name = "Modèle"
    print(results_df.to_string())

    # ── Étape 5 : Sélection du meilleur modèle ────────────────────────────────
    best_name = results_df["f1_score"].idxmax()
    best_model = trained_models[best_name]
    best_metrics = results[best_name]

    print("\n" + "=" * 60)
    print("  ÉTAPE 5 : Sélection du meilleur modèle")
    print("=" * 60)
    print(f"\n  ✅ Meilleur modèle : {best_name}")
    print(f"     F1-Score  : {best_metrics['f1_score']:.4f}")
    print(f"     Accuracy  : {best_metrics['accuracy']:.4f}")
    print(f"     Précision : {best_metrics['precision']:.4f}")
    print(f"     Rappel    : {best_metrics['recall']:.4f}")

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    with open(BEST_MODEL_PATH, "wb") as f:
        pickle.dump(best_model, f)
    print(f"\n  💾 Modèle sauvegardé → {BEST_MODEL_PATH}")

    return best_name, best_model, results_df


if __name__ == "__main__":
    train_and_select()
