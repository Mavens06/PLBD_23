"""Evaluate trained Agri-Botics model artifacts and refresh documentation."""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split

try:
    from .model_registry import (
        EMBEDDED_FEATURES, EMBEDDED_MODEL_PATH, FULL_FEATURES, FULL_MODEL_PATH, METRICS_PATH,
        MODEL_METADATA_PATH, PROCESSED_DIR, ensure_dirs, now_iso, read_json, write_json,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model_registry import (
        EMBEDDED_FEATURES, EMBEDDED_MODEL_PATH, FULL_FEATURES, FULL_MODEL_PATH, METRICS_PATH,
        MODEL_METADATA_PATH, PROCESSED_DIR, ensure_dirs, now_iso, read_json, write_json,
    )

FULL_CSV = PROCESSED_DIR / "processed_full_crop_model.csv"
EMBEDDED_CSV = PROCESSED_DIR / "processed_embedded_robot_model.csv"
MODEL_CARD = Path(__file__).resolve().parent.parent / "MODEL_CARD.md"


def _eval_one(name: str, model_path: Path, csv_path: Path, features: list[str]) -> dict:
    if not model_path.exists() or not csv_path.exists():
        return {"available": False, "reason": "model or dataset missing"}
    df = pd.read_csv(csv_path).dropna(subset=features + ["label"])
    if len(df) < 10 or df["label"].nunique() < 2:
        return {"available": False, "reason": "not enough evaluation data"}
    X = df[features].astype(float)
    y = df["label"].astype(str)
    stratify = y if y.value_counts().min() >= 2 else None
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=stratify)
    with model_path.open("rb") as f:
        model = pickle.load(f)
    pred = model.predict(X_test)
    return {
        "available": True,
        "model": name,
        "artifact": str(model_path),
        "dataset": str(csv_path),
        "features": features,
        "rows_evaluated": int(len(X_test)),
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "f1_macro": round(float(f1_score(y_test, pred, average="macro", zero_division=0)), 4),
        "classification_report": classification_report(y_test, pred, output_dict=True, zero_division=0),
    }


def _write_model_card(results: dict) -> None:
    sources = read_json(Path("data/metadata/sources.json"), [])
    audit = read_json(Path("data/metadata/dataset_audit.json"), {})
    lines = [
        "# Agri-Botics Model Card",
        "",
        f"Generated: {now_iso()}",
        "",
        "## Purpose",
        "",
        "Agri-Botics uses crop recommendation models as decision support. The robot-facing recommendation never requires N/P/K/rainfall; it uses only temperature, humidity, pH, and EC, then applies the agronomic rules engine as a guardrail.",
        "",
        "## Datasets",
        "",
    ]
    if isinstance(sources, list) and sources:
        for src in sources[-12:]:
            lines.append(f"- {src.get('name')}: {src.get('status')} ({src.get('source')}) -> {src.get('local_path')}")
    else:
        lines.append("- No external source metadata recorded yet.")
    lines.extend([
        "",
        "## Processed Tables",
        "",
        "- `data/processed/processed_full_crop_model.csv`: audited only. It contains N/P/K/rainfall and is not used by the robot model.",
        "- `data/processed/processed_embedded_robot_model.csv`: production robot ML table built from the real CSV after dropping N/P/K/rainfall. Features: temperature, humidity, pH. EC is used by rules/alerts, not by this CSV-trained ML model.",
        "- `data/processed/processed_sensor_calibration.csv`: optional sensor calibration table. It is not used for crop classification unless a crop label is present and meaningful.",
        "",
        "## Models",
        "",
        "### Full experimental model",
        "",
        "Disabled by default. These features include `N`, `P`, `K` and `rainfall`, which the robot does not measure. The table is kept for audit/research only and is not a backend production model.",
        "",
        "### Embedded robot model",
        "",
        "Features: `temperature`, `humidity`, `ph`. This is the default robot-facing ML model trained from the real CSV. The robot still sends EC, but EC is consumed by `ml_model/rules/engine.py` as a guardrail because the real CSV does not contain measured EC.",
        "",
        "## Metrics",
        "",
    ])
    for key in ["full_model", "embedded_model"]:
        r = results.get(key, {})
        if r.get("available"):
            lines.append(f"- {key}: accuracy={r.get('accuracy')}, f1_macro={r.get('f1_macro')}, rows_evaluated={r.get('rows_evaluated')}")
        else:
            lines.append(f"- {key}: unavailable ({r.get('reason')})")
    lines.extend([
        "",
        "## Role of rules",
        "",
        "The ML model proposes a top-3. The rules engine checks pH, humidity, temperature, and EC against crop ranges. Inconsistent high-confidence ML suggestions are penalized or flagged instead of blindly accepted.",
        "",
        "## Current limitations",
        "",
        "- Public crop datasets contain N/P/K/rainfall but no measured EC. Those non-measured columns are dropped for the robot model; EC is handled by rules until real EC-labeled data exists.",
        "- Sensor calibration datasets without crop labels must not be used directly for crop classification.",
        "- Metrics on synthetic/catalog data are not equivalent to field validation.",
        "",
        "## Future improvements with real sensors",
        "",
        "- Replace estimated/synthetic EC rows with measured EC from the RS485 probe.",
        "- Persist field sessions and use confirmed farmer outcomes as labels.",
        "- Expand `crop_catalog.py` only when source ranges are documented and compatible with Moroccan crops.",
    ])
    MODEL_CARD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def evaluate_all() -> dict:
    ensure_dirs()
    results = {
        "generated_at": now_iso(),
        "full_model": {
            "available": False,
            "deployable": False,
            "reason": "disabled: N/P/K/rainfall are not measured by the robot",
            "features": FULL_FEATURES,
        },
        "embedded_model": _eval_one("embedded_model", EMBEDDED_MODEL_PATH, EMBEDDED_CSV, EMBEDDED_FEATURES),
    }
    existing = read_json(METRICS_PATH, {})
    existing["evaluation"] = results
    write_json(METRICS_PATH, existing)
    metadata = read_json(MODEL_METADATA_PATH, {})
    metadata["last_evaluation"] = results
    write_json(MODEL_METADATA_PATH, metadata)
    _write_model_card(results)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results


if __name__ == "__main__":
    evaluate_all()
