"""Model artifact registry for Agri-Botics ML pipelines."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ML_DIR = ROOT / "ml_model"
DATA_DIR = ROOT / "data"
MODELS_DIR = ML_DIR / "models"
METADATA_DIR = DATA_DIR / "metadata"
PROCESSED_DIR = DATA_DIR / "processed"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
REAL_DIR = DATA_DIR / "real"
RAW_DIR = DATA_DIR / "raw"
EXTERNAL_DIR = DATA_DIR / "external"

FULL_MODEL_PATH = MODELS_DIR / "full_model.pkl"
FULL_METADATA_PATH = MODELS_DIR / "full_model_metadata.json"
EMBEDDED_MODEL_PATH = MODELS_DIR / "embedded_model.pkl"
EMBEDDED_METADATA_PATH = MODELS_DIR / "embedded_model_metadata.json"
METRICS_PATH = ML_DIR / "metrics.json"
MODEL_METADATA_PATH = ML_DIR / "model_metadata.json"

LEGACY_MODEL_PATH = ML_DIR / "best_model.pkl"
LEGACY_SCALER_PATH = ML_DIR / "scaler.pkl"

FULL_FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
EMBEDDED_FEATURES = ["temperature", "humidity", "ph"]
TARGET_CANDIDATES = ["label", "crop", "culture", "target"]


def ensure_dirs() -> None:
    for path in [MODELS_DIR, METADATA_DIR, PROCESSED_DIR, SYNTHETIC_DIR, REAL_DIR, RAW_DIR, EXTERNAL_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
