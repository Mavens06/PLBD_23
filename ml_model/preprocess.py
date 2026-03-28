# =============================================================================
# preprocess.py
# Prétraitement du dataset de recommandation de cultures :
#   - Gestion des valeurs manquantes
#   - Séparation des features (X) et de la cible (y)
#   - Division entraînement / test (train_test_split)
#   - Normalisation des features avec StandardScaler
#   - Sauvegarde du scaler ajusté avec joblib pour les prédictions futures
# =============================================================================

import os
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Chemin de sauvegarde du scaler ajusté
SCALER_PATH = os.path.join(os.path.dirname(__file__), "scaler.pkl")

# Colonnes utilisées comme features (capteurs physiques / chimiques)
FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]

# Colonne cible (culture à recommander)
TARGET = "label"


def gerer_valeurs_manquantes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gère les valeurs manquantes dans le dataset.
    Stratégie : remplacement par la médiane pour les colonnes numériques.

    Paramètres
    ----------
    df : DataFrame brut.

    Retourne
    --------
    pd.DataFrame : DataFrame nettoyé sans valeurs manquantes.
    """
    nb_manquants = df.isnull().sum().sum()
    if nb_manquants > 0:
        print(f"[INFO] {nb_manquants} valeur(s) manquante(s) détectée(s) → remplacement par la médiane.")
        for col in df.select_dtypes(include="number").columns:
            df[col] = df[col].fillna(df[col].median())
    else:
        print("[INFO] Aucune valeur manquante détectée.")
    return df


def preparer_donnees(
    df: pd.DataFrame,
    taille_test: float = 0.2,
    graine: int = 42,
    sauvegarder_scaler: bool = True,
):
    """
    Pipeline complet de prétraitement :
        1. Nettoyage des valeurs manquantes
        2. Séparation features / cible
        3. Division train / test
        4. Normalisation avec StandardScaler
        5. Sauvegarde du scaler

    Paramètres
    ----------
    df               : DataFrame chargé depuis data_loader.
    taille_test      : Proportion du jeu de test (par défaut 20 %).
    graine           : Graine aléatoire pour la reproductibilité.
    sauvegarder_scaler : Si True, sauvegarde le scaler dans SCALER_PATH.

    Retourne
    --------
    X_train_sc, X_test_sc, y_train, y_test : Données prêtes pour l'entraînement.
    """
    # Étape 1 : Nettoyage
    df = gerer_valeurs_manquantes(df)

    # Étape 2 : Séparation features / cible
    X = df[FEATURES]
    y = df[TARGET]

    print(f"[INFO] Features utilisées : {FEATURES}")
    print(f"[INFO] Taille totale du dataset : {len(df)} échantillons")

    # Étape 3 : Division entraînement / test (stratifiée pour équilibrer les classes)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=taille_test,
        random_state=graine,
        stratify=y,
    )
    print(f"[INFO] Entraînement : {len(X_train)} | Test : {len(X_test)}")

    # Étape 4 : Normalisation (ajustement uniquement sur les données d'entraînement)
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc = scaler.transform(X_test)

    # Étape 5 : Sauvegarde du scaler pour les prédictions futures (API, ESP32, etc.)
    if sauvegarder_scaler:
        joblib.dump(scaler, SCALER_PATH)
        print(f"[INFO] Scaler sauvegardé dans : {SCALER_PATH}")

    return X_train_sc, X_test_sc, y_train, y_test


def charger_scaler(chemin: str = SCALER_PATH) -> StandardScaler:
    """
    Charge le scaler précédemment sauvegardé pour l'utiliser en production.

    Paramètres
    ----------
    chemin : Chemin vers le fichier .pkl du scaler.

    Retourne
    --------
    StandardScaler : Scaler prêt à transformer de nouvelles données.
    """
    if not os.path.exists(chemin):
        raise FileNotFoundError(
            f"Scaler introuvable à '{chemin}'. Lancez d'abord train.py."
        )
    scaler = joblib.load(chemin)
    print(f"[INFO] Scaler chargé depuis : {chemin}")
    return scaler


# --- Exécution directe pour test rapide ---
if __name__ == "__main__":
    from data_loader import charger_donnees

    df = charger_donnees()
    X_train, X_test, y_train, y_test = preparer_donnees(df)
    print("\n[OK] Prétraitement terminé.")
    print(f"     X_train shape : {X_train.shape}")
    print(f"     X_test  shape : {X_test.shape}")
