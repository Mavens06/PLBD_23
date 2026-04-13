"""
preprocess.py
-------------
Charge le dataset des cultures marocaines, sépare features et cible,
gère les valeurs manquantes, normalise les features avec StandardScaler,
et sauvegarde le scaler pour une utilisation future (prédictions en temps réel).

Utilisation :
    python ml_model/preprocess.py
"""

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# ── Chemins ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH    = os.path.join(SCRIPT_DIR, "moroccan_crop_data.csv")
SCALER_PATH = os.path.join(SCRIPT_DIR, "scaler.pkl")

# ── Colonnes features ──────────────────────────────────────────────────────────
FEATURE_COLS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall", "salinity"]
TARGET_COL   = "label"

# Ratio de séparation Train / Test
TEST_SIZE  = 0.20
RANDOM_STATE = 42


def load_and_split(csv_path: str = CSV_PATH):
    """
    Charge le CSV, sépare X et y, gère les valeurs manquantes.
    Retourne : X_train, X_test, y_train, y_test (non scalés).
    """
    # ── Chargement ─────────────────────────────────────────────────────────────
    if not os.path.exists(csv_path):
        # Générer le dataset à la volée si le CSV n'existe pas encore
        print(f"[preprocess] CSV introuvable ({csv_path}). Génération du dataset...")
        from data_loader import generate_dataset
        generate_dataset(output_path=csv_path)

    df = pd.read_csv(csv_path)
    print(f"[preprocess] Dataset chargé : {df.shape[0]} lignes, {df.shape[1]} colonnes.")

    # ── Vérification des colonnes ───────────────────────────────────────────────
    missing_cols = [c for c in FEATURE_COLS + [TARGET_COL] if c not in df.columns]
    if missing_cols:
        raise ValueError(f"[preprocess] Colonnes manquantes dans le CSV : {missing_cols}")

    # ── Gestion des valeurs manquantes ──────────────────────────────────────────
    n_missing = df[FEATURE_COLS].isnull().sum().sum()
    if n_missing > 0:
        print(f"[preprocess] {n_missing} valeur(s) manquante(s) détectée(s) → remplacement par la médiane.")
        for col in FEATURE_COLS:
            df.loc[:, col] = df[col].fillna(df[col].median())

    # ── Séparation features / cible ─────────────────────────────────────────────
    X = df[FEATURE_COLS].values.astype(np.float32)
    y = df[TARGET_COL].values

    # ── Séparation Train / Test ─────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    print(f"[preprocess] Train : {X_train.shape[0]} lignes | Test : {X_test.shape[0]} lignes.")
    return X_train, X_test, y_train, y_test


def scale_features(X_train, X_test, scaler_path: str = SCALER_PATH):
    """
    Applique StandardScaler sur X_train et transforme X_test.
    Sauvegarde le scaler ajusté (fit) pour les prédictions futures.
    Retourne : X_train_scaled, X_test_scaled, scaler.
    """
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)

    # ── Sauvegarde du scaler ────────────────────────────────────────────────────
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    print(f"[preprocess] Scaler sauvegardé → {scaler_path}")

    return X_train_scaled, X_test_scaled, scaler


def preprocess(csv_path: str = CSV_PATH, scaler_path: str = SCALER_PATH):
    """
    Pipeline complet de prétraitement.
    Retourne : X_train_scaled, X_test_scaled, y_train, y_test, scaler.
    """
    X_train, X_test, y_train, y_test = load_and_split(csv_path)
    X_train_s, X_test_s, scaler = scale_features(X_train, X_test, scaler_path)
    return X_train_s, X_test_s, y_train, y_test, scaler


if __name__ == "__main__":
    X_tr, X_te, y_tr, y_te, sc = preprocess()
    print(f"\n[preprocess] Dimensions :")
    print(f"  X_train : {X_tr.shape}")
    print(f"  X_test  : {X_te.shape}")
    print(f"  Classes : {sorted(set(y_tr))}")
