"""
train.py
--------
Entraîne un modèle de recommandation de cultures SANS N/P/K à partir du
fichier ml_model/data/final_dataset.csv.

Artefacts sauvegardés:
  ml_model/models/model.pkl
  ml_model/models/scaler.pkl
  ml_model/models/label_encoder.pkl
"""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from data_preparation import create_final_dataset

SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_PATH = SCRIPT_DIR / "data" / "final_dataset.csv"
MODELS_DIR = SCRIPT_DIR / "models"
MODEL_PATH = MODELS_DIR / "model.pkl"
SCALER_PATH = MODELS_DIR / "scaler.pkl"
LABEL_ENCODER_PATH = MODELS_DIR / "label_encoder.pkl"

RANDOM_STATE = 42
BASE_FEATURES = ["temperature", "humidity", "ph", "rainfall"]
OPTIONAL_FEATURES = ["salinity", "soil_moisture"]
TARGET_COL = "label"


def _load_dataset() -> pd.DataFrame:
    if not DATASET_PATH.exists():
        print(f"[train] Dataset absent, génération: {DATASET_PATH}")
        create_final_dataset(output_path=DATASET_PATH)
    df = pd.read_csv(DATASET_PATH)
    print(f"[train] Dataset chargé: {df.shape[0]} lignes, {df.shape[1]} colonnes")
    return df


def train() -> None:
    df = _load_dataset()

    missing = [c for c in BASE_FEATURES + [TARGET_COL] if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes dans final_dataset.csv: {missing}")

    features = BASE_FEATURES + [c for c in OPTIONAL_FEATURES if c in df.columns]
    print(f"[train] Features utilisées: {features}")

    X = df[features].copy()
    for col in features:
        X[col] = pd.to_numeric(X[col], errors="coerce")
        if X[col].isna().any():
            X[col] = X[col].fillna(X[col].median())

    y = df[TARGET_COL].astype(str).str.strip()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    label_encoder = LabelEncoder()
    y_train_encoded = label_encoder.fit_transform(y_train)
    y_test_encoded = label_encoder.transform(y_test)

    model = RandomForestClassifier(
        n_estimators=400,
        random_state=RANDOM_STATE,
        class_weight="balanced",
        n_jobs=-1,
    )
    model.fit(X_train_scaled, y_train_encoded)

    y_pred = model.predict(X_test_scaled)
    acc = accuracy_score(y_test_encoded, y_pred)
    f1 = f1_score(y_test_encoded, y_pred, average="weighted")

    print(f"[train] Accuracy: {acc:.4f}")
    print(f"[train] F1-weighted: {f1:.4f}")
    print("[train] Rapport:\n" + classification_report(
        y_test_encoded,
        y_pred,
        target_names=label_encoder.classes_,
        zero_division=0,
    ))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    joblib.dump(label_encoder, LABEL_ENCODER_PATH)

    print(f"[train] Modèle sauvegardé -> {MODEL_PATH}")
    print(f"[train] Scaler sauvegardé -> {SCALER_PATH}")
    print(f"[train] LabelEncoder sauvegardé -> {LABEL_ENCODER_PATH}")


if __name__ == "__main__":
    train()
