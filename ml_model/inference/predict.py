from __future__ import annotations

import os
import pickle
from functools import lru_cache
from typing import Dict, List

import numpy as np

from ml_model.feature_mapping import to_ml_features, to_runtime_features
from ml_model.rules.engine import recommend_actions, recommend_crops

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(SCRIPT_DIR, 'best_model.pkl')
SCALER_PATH = os.path.join(SCRIPT_DIR, 'scaler.pkl')
DEFAULT_FEATURE_ORDER = ['temperature', 'humidity', 'ph', 'rainfall', 'salinity']


@lru_cache(maxsize=1)
def _load_artifacts():
    if not (os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH)):
        return None, None
    with open(MODEL_PATH, 'rb') as f:
        model = pickle.load(f)
    with open(SCALER_PATH, 'rb') as f:
        scaler = pickle.load(f)
    return model, scaler


def _title_case_label(label: str) -> str:
    return ' '.join(part.capitalize() for part in str(label).strip().split())


def _build_vector(sensor_data: Dict[str, float], scaler) -> np.ndarray:
    ml_data = to_ml_features(sensor_data=sensor_data, rainfall=sensor_data.get('rainfall', 0.0))
    feature_order = DEFAULT_FEATURE_ORDER[: getattr(scaler, 'n_features_in_', len(DEFAULT_FEATURE_ORDER))]
    row = [float(ml_data.get(name, 0.0)) for name in feature_order]
    return np.array([row], dtype=np.float32)


def _predict_top_crops_ml(sensor_data: Dict[str, float], top_n: int = 5) -> List[dict]:
    model, scaler = _load_artifacts()
    if model is None or scaler is None:
        return []

    X = _build_vector(sensor_data, scaler)
    X_scaled = scaler.transform(X)

    if hasattr(model, 'predict_proba'):
        proba = model.predict_proba(X_scaled)[0]
        labels = model.classes_
        top_idx = np.argsort(proba)[::-1][:max(1, top_n)]
        return [
            {'name': _title_case_label(labels[i]), 'score': round(float(proba[i]) * 100, 1)}
            for i in top_idx
        ]

    label = model.predict(X_scaled)[0]
    return [{'name': _title_case_label(label), 'score': None}]


def predict(sensor_data: dict):
    runtime_data = to_runtime_features(sensor_data)
    top_crops_ml = _predict_top_crops_ml(sensor_data, top_n=5)
    fallback_crops = recommend_crops(runtime_data, top_n=5)
    top_crops = top_crops_ml or fallback_crops

    alerts = [
        'Humidité faible' if runtime_data.get('humidity', 0) < 40 else None,
        'Conductivité élevée' if runtime_data.get('ec', 0) > 2.5 else None,
        'pH hors plage' if not 5.8 <= runtime_data.get('ph', 6.5) <= 7.8 else None,
    ]

    return {
        'source': 'ml' if top_crops_ml else 'rules',
        'top_crops': top_crops,
        'actions': recommend_actions(runtime_data),
        'alerts': [a for a in alerts if a],
    }
