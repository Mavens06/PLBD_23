"""
preprocess.py
-------------
Charge le dataset final, sépare features/cible, applique StandardScaler.
Le scaler ajusté est sauvegardé pour réutilisation à l'inférence
(ml_model/predict.py et /api/recommendation).

Ordre canonique des features (partagé avec data_loader.FEATURE_ORDER
et ml_model/predict.py) :
    ["ph", "humidity", "temperature", "ec"]

Utilisation :
    python ml_model/preprocess.py
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from data_loader import FEATURE_ORDER
from data_preparation import create_final_dataset


SCRIPT_DIR = Path(__file__).resolve().parent
CSV_PATH = SCRIPT_DIR / "data" / "final_dataset.csv"
SCALER_PATH = SCRIPT_DIR / "scaler.pkl"

TARGET_COL = "label"
TEST_SIZE = 0.20
RANDOM_STATE = 42


def load_and_split(csv_path: str | os.PathLike = CSV_PATH) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Charge le CSV, vérifie le périmètre 4 variables, split train/test stratifié."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"[preprocess] CSV introuvable ({csv_path}). Génération...")
        create_final_dataset(output_path=csv_path)

    df = pd.read_csv(csv_path)
    print(f"[preprocess] Dataset chargé : {df.shape[0]} lignes, {df.shape[1]} colonnes.")

    missing = [c for c in FEATURE_ORDER + [TARGET_COL] if c not in df.columns]
    if missing:
        raise ValueError(f"[preprocess] Colonnes requises absentes : {missing}")

    forbidden = {"N", "P", "K", "rainfall"} & set(df.columns)
    if forbidden:
        raise ValueError(
            f"[preprocess] Colonnes hors périmètre détectées : {sorted(forbidden)}. "
            "Lancer data_preparation.py pour régénérer un dataset propre."
        )

    X = df[FEATURE_ORDER].values.astype(np.float32)
    y = df[TARGET_COL].astype(str).values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y,
    )
    print(f"[preprocess] Train : {X_train.shape[0]} | Test : {X_test.shape[0]} | classes : {len(set(y))}")
    return X_train, X_test, y_train, y_test


def scale_features(
    X_train: np.ndarray,
    X_test: np.ndarray,
    scaler_path: str | os.PathLike = SCALER_PATH,
) -> Tuple[np.ndarray, np.ndarray, StandardScaler]:
    """Ajuste StandardScaler sur X_train, transforme X_test, sauvegarde sur disque."""
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    print(f"[preprocess] Scaler sauvegardé → {scaler_path}")
    return X_train_s, X_test_s, scaler


def preprocess(
    csv_path: str | os.PathLike = CSV_PATH,
    scaler_path: str | os.PathLike = SCALER_PATH,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, StandardScaler]:
    """Pipeline complet : load → split → scale."""
    X_train, X_test, y_train, y_test = load_and_split(csv_path)
    X_train_s, X_test_s, scaler = scale_features(X_train, X_test, scaler_path)
    return X_train_s, X_test_s, y_train, y_test, scaler


if __name__ == "__main__":
    X_tr, X_te, y_tr, y_te, sc = preprocess()
    print(f"\n[preprocess] Dimensions : X_train={X_tr.shape} | X_test={X_te.shape}")
    print(f"[preprocess] Classes : {sorted(set(y_tr))}")
