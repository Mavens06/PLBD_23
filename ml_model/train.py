# =============================================================================
# train.py
# Pipeline d'entraînement et de sélection du meilleur modèle ML pour la
# recommandation agricole de cultures.
#
# Modèles comparés :
#   - Random Forest Classifier
#   - Support Vector Classifier (SVC)
#   - Gradient Boosting Classifier
#   - Logistic Regression
#
# Métriques d'évaluation (pondérées par classe) :
#   - Accuracy  : taux de bonnes prédictions globales
#   - Precision : capacité à ne pas classer un mauvais label comme positif
#   - Recall    : capacité à retrouver tous les vrais positifs
#   - F1-Score  : moyenne harmonique de la précision et du rappel (critère de sélection)
#
# Le meilleur modèle (F1-Score le plus élevé) est sauvegardé dans best_model.pkl.
# =============================================================================

import os
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)

from data_loader import charger_donnees
from preprocess import preparer_donnees

# Chemin de sauvegarde du meilleur modèle
MEILLEUR_MODELE_PATH = os.path.join(os.path.dirname(__file__), "best_model.pkl")


def definir_modeles() -> dict:
    """
    Définit et retourne le dictionnaire des modèles à comparer.
    Chaque valeur est une instance (non entraînée) du classifieur.

    Retourne
    --------
    dict : {nom_du_modele: instance_du_modele}
    """
    return {
        "Random Forest": RandomForestClassifier(
            n_estimators=200,
            random_state=42,
            n_jobs=-1,
        ),
        "SVC": SVC(
            kernel="rbf",
            C=10,
            gamma="scale",
            random_state=42,
        ),
        "Gradient Boosting": GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.1,
            max_depth=5,
            random_state=42,
        ),
        "Logistic Regression": LogisticRegression(
            max_iter=1000,
            random_state=42,
            n_jobs=-1,
        ),
    }


def evaluer_modele(modele, X_test, y_test) -> dict:
    """
    Évalue un modèle entraîné sur le jeu de test et retourne les métriques clés.

    Paramètres
    ----------
    modele : Classifieur scikit-learn déjà entraîné.
    X_test : Features du jeu de test (normalisées).
    y_test : Labels réels du jeu de test.

    Retourne
    --------
    dict : {'accuracy', 'precision', 'recall', 'f1'}
    """
    y_pred = modele.predict(X_test)
    return {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, average="weighted", zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, average="weighted", zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, average="weighted", zero_division=0), 4),
    }


def afficher_rapport(resultats: dict) -> None:
    """
    Affiche un tableau comparatif des performances de tous les modèles.

    Paramètres
    ----------
    resultats : {nom_modele: {'accuracy', 'precision', 'recall', 'f1'}}
    """
    print("\n" + "=" * 70)
    print(f"{'RAPPORT COMPARATIF DES MODÈLES':^70}")
    print("=" * 70)
    entete = f"{'Modèle':<25} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1-Score':>10}"
    print(entete)
    print("-" * 70)
    for nom, metriques in resultats.items():
        print(
            f"{nom:<25} "
            f"{metriques['accuracy']:>10.4f} "
            f"{metriques['precision']:>10.4f} "
            f"{metriques['recall']:>10.4f} "
            f"{metriques['f1']:>10.4f}"
        )
    print("=" * 70)


def selectionner_meilleur_modele(modeles_entraines: dict, resultats: dict) -> tuple:
    """
    Identifie le modèle avec le F1-Score le plus élevé.

    Paramètres
    ----------
    modeles_entraines : {nom: modele_entraîné}
    resultats         : {nom: metriques}

    Retourne
    --------
    tuple : (nom_du_meilleur, modele_meilleur, metriques_meilleures)
    """
    meilleur_nom = max(resultats, key=lambda n: resultats[n]["f1"])
    return meilleur_nom, modeles_entraines[meilleur_nom], resultats[meilleur_nom]


def entrainer_et_selectionner() -> None:
    """
    Pipeline complet :
        1. Chargement des données
        2. Prétraitement
        3. Entraînement de tous les modèles
        4. Évaluation et rapport comparatif
        5. Sélection du meilleur modèle (F1-Score)
        6. Sauvegarde du meilleur modèle
    """
    # -------------------------------------------------------------------------
    # Étape 1 : Chargement du dataset
    # -------------------------------------------------------------------------
    print("\n[ÉTAPE 1] Chargement du dataset...")
    df = charger_donnees()

    # -------------------------------------------------------------------------
    # Étape 2 : Prétraitement
    # -------------------------------------------------------------------------
    print("\n[ÉTAPE 2] Prétraitement des données...")
    X_train, X_test, y_train, y_test = preparer_donnees(df)

    # -------------------------------------------------------------------------
    # Étape 3 : Entraînement de tous les modèles
    # -------------------------------------------------------------------------
    print("\n[ÉTAPE 3] Entraînement des modèles...")
    modeles = definir_modeles()
    modeles_entraines = {}
    resultats = {}

    for nom, modele in modeles.items():
        print(f"   → Entraînement : {nom} ...")
        modele.fit(X_train, y_train)
        modeles_entraines[nom] = modele

        # -------------------------------------------------------------------------
        # Étape 4 : Évaluation
        # -------------------------------------------------------------------------
        resultats[nom] = evaluer_modele(modele, X_test, y_test)
        print(f"      F1-Score = {resultats[nom]['f1']:.4f}")

    # -------------------------------------------------------------------------
    # Étape 5 : Rapport comparatif
    # -------------------------------------------------------------------------
    afficher_rapport(resultats)

    # -------------------------------------------------------------------------
    # Étape 6 : Sélection et sauvegarde du meilleur modèle
    # -------------------------------------------------------------------------
    meilleur_nom, meilleur_modele, meilleures_metriques = selectionner_meilleur_modele(
        modeles_entraines, resultats
    )

    print(f"\n[RÉSULTAT] Meilleur modèle sélectionné : {meilleur_nom}")
    print(f"           F1-Score  : {meilleures_metriques['f1']:.4f}")
    print(f"           Accuracy  : {meilleures_metriques['accuracy']:.4f}")
    print(f"           Precision : {meilleures_metriques['precision']:.4f}")
    print(f"           Recall    : {meilleures_metriques['recall']:.4f}")

    joblib.dump(meilleur_modele, MEILLEUR_MODELE_PATH)
    print(f"\n[OK] Meilleur modèle sauvegardé dans : {MEILLEUR_MODELE_PATH}")


# --- Point d'entrée principal ---
if __name__ == "__main__":
    entrainer_et_selectionner()
