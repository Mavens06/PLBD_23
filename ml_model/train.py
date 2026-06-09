"""Train full experimental and embedded robot crop recommendation models.

This script does not delete or overwrite the legacy `best_model.pkl` pipeline.
New artifacts are written under `ml_model/models/`:
- full_model.pkl is NOT trained by default because it depends on N/P/K/rainfall,
  which the robot does not measure.
- embedded_model.pkl is the production robot model. It uses the real CSV with
  only measured/available ML columns: temperature, humidity, and pH. EC is
  handled by rules at inference time.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from .model_registry import (
        EMBEDDED_FEATURES, EMBEDDED_METADATA_PATH, EMBEDDED_MODEL_PATH, FULL_FEATURES,
        FULL_METADATA_PATH, FULL_MODEL_PATH, METRICS_PATH, MODEL_METADATA_PATH, PROCESSED_DIR,
        ensure_dirs, now_iso, write_json,
    )
    from .prepare_dataset import prepare
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model_registry import (
        EMBEDDED_FEATURES, EMBEDDED_METADATA_PATH, EMBEDDED_MODEL_PATH, FULL_FEATURES,
        FULL_METADATA_PATH, FULL_MODEL_PATH, METRICS_PATH, MODEL_METADATA_PATH, PROCESSED_DIR,
        ensure_dirs, now_iso, write_json,
    )
    from prepare_dataset import prepare

RANDOM_STATE = 42
FULL_CSV = PROCESSED_DIR / "processed_full_crop_model.csv"
EMBEDDED_CSV = PROCESSED_DIR / "processed_embedded_robot_model.csv"


def _models() -> dict[str, Any]:
    return {
        "RandomForest": RandomForestClassifier(n_estimators=250, random_state=RANDOM_STATE, n_jobs=-1, class_weight="balanced"),
        "GradientBoosting": GradientBoostingClassifier(random_state=RANDOM_STATE),
        "ExtraTrees": ExtraTreesClassifier(n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1, class_weight="balanced"),
    }


def _top_k_accuracy(model: Pipeline, X_test: pd.DataFrame, y_test: pd.Series, k: int = 3) -> float | None:
    clf = model.named_steps["model"]
    if not hasattr(clf, "predict_proba"):
        return None
    probs = model.predict_proba(X_test)
    classes = np.asarray(model.classes_)
    top = classes[np.argsort(-probs, axis=1)[:, :k]]
    return round(float(np.mean([yt in row for yt, row in zip(np.asarray(y_test), top)])), 4)


def _train_one(name: str, csv_path: Path, features: list[str], model_path: Path, metadata_path: Path, min_rows: int = 30) -> dict:
    if not csv_path.exists():
        return {"trained": False, "reason": f"missing dataset: {csv_path}", "path": str(csv_path)}
    df = pd.read_csv(csv_path)
    missing = [c for c in features + ["label"] if c not in df.columns]
    if missing:
        return {"trained": False, "reason": f"missing columns: {missing}", "path": str(csv_path)}
    df = df.dropna(subset=features + ["label"])
    if len(df) < min_rows or df["label"].nunique() < 2:
        return {"trained": False, "reason": "not enough rows/classes", "rows": int(len(df)), "classes": int(df['label'].nunique()) if len(df) else 0}

    X = df[features].astype(float)
    y = df["label"].astype(str)
    stratify = y if y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=stratify)

    candidates = {}
    trained = {}
    for model_name, estimator in _models().items():
        pipe = Pipeline([("scaler", StandardScaler()), ("model", estimator)])
        t0 = time.time()
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)
        metrics = {
            "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
            "f1_macro": round(float(f1_score(y_test, y_pred, average="macro", zero_division=0)), 4),
            "top3_accuracy": _top_k_accuracy(pipe, X_test, y_test, 3),
            "fit_time_s": round(time.time() - t0, 2),
        }
        candidates[model_name] = metrics
        trained[model_name] = pipe

    best_name = sorted(candidates, key=lambda n: (candidates[n]["f1_macro"], candidates[n]["accuracy"]), reverse=True)[0]
    best_model = trained[best_name]
    y_pred = best_model.predict(X_test)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with model_path.open("wb") as f:
        pickle.dump(best_model, f)

    metadata = {
        "model_type": name,
        "trained_at": now_iso(),
        "artifact": str(model_path),
        "dataset": str(csv_path),
        "rows": int(len(df)),
        "classes": sorted(y.unique().tolist()),
        "features": features,
        "best_model": best_name,
        "candidate_metrics": candidates,
        "classification_report": classification_report(y_test, y_pred, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=best_model.classes_).tolist(),
        "confusion_matrix_labels": list(best_model.classes_),
    }
    write_json(metadata_path, metadata)
    return {"trained": True, **metadata}


def _disabled_full_model() -> dict:
    rows = 0
    if FULL_CSV.exists():
        try:
            rows = int(len(pd.read_csv(FULL_CSV)))
        except Exception:
            rows = 0
    return {
        "trained": False,
        "deployable": False,
        "reason": "disabled: N/P/K/rainfall are not measured by the robot",
        "dataset": str(FULL_CSV),
        "rows": rows,
        "features": FULL_FEATURES,
    }


def train_all(run_prepare: bool = True, train_full_experimental: bool = False) -> dict:
    ensure_dirs()
    if run_prepare:
        prepare()
    full = _train_one("full_experimental", FULL_CSV, FULL_FEATURES, FULL_MODEL_PATH, FULL_METADATA_PATH) if train_full_experimental else _disabled_full_model()
    embedded = _train_one("embedded_robot", EMBEDDED_CSV, EMBEDDED_FEATURES, EMBEDDED_MODEL_PATH, EMBEDDED_METADATA_PATH)
    metrics = {"generated_at": now_iso(), "full_model": full, "embedded_model": embedded}
    write_json(METRICS_PATH, metrics)
    write_json(MODEL_METADATA_PATH, {
        "generated_at": now_iso(),
        "models": {
            "full_model": {"artifact": str(FULL_MODEL_PATH), "features": FULL_FEATURES, "trained": full.get("trained", False), "deployable": False, "reason": full.get("reason")},
            "embedded_model": {"artifact": str(EMBEDDED_MODEL_PATH), "features": EMBEDDED_FEATURES, "trained": embedded.get("trained", False), "deployable": True},
            "legacy_model": {"artifact": "ml_model/best_model.pkl", "preserved": True},
        },
        "safety": "Robot inference never requires N/P/K/rainfall. Rules remain the agronomic guardrail.",
    })
    print(json.dumps({"full_trained": full.get("trained"), "embedded_trained": embedded.get("trained")}, ensure_ascii=False, indent=2))
    return metrics


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train Agri-Botics ML models")
    parser.add_argument("--no-prepare", action="store_true", help="Use existing processed CSV files")
    parser.add_argument("--train-full-experimental", action="store_true", help="Also train the non-deployable N/P/K/rainfall model for research only")
    args = parser.parse_args()
    train_all(run_prepare=not args.no_prepare, train_full_experimental=args.train_full_experimental)
