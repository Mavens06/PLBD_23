"""Audit and prepare real, external, and synthetic datasets for Agri-Botics."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

try:
    from .model_registry import (
        DATA_DIR, EXTERNAL_DIR, FULL_FEATURES, METADATA_DIR, PROCESSED_DIR, RAW_DIR, REAL_DIR,
        SYNTHETIC_DIR, TARGET_CANDIDATES, ensure_dirs, now_iso, write_json,
    )
    from .rules.crop_catalog import CROP_CATALOG
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model_registry import (
        DATA_DIR, EXTERNAL_DIR, FULL_FEATURES, METADATA_DIR, PROCESSED_DIR, RAW_DIR, REAL_DIR,
        SYNTHETIC_DIR, TARGET_CANDIDATES, ensure_dirs, now_iso, write_json,
    )
    from rules.crop_catalog import CROP_CATALOG

AUDIT_JSON = METADATA_DIR / "dataset_audit.json"
AUDIT_MD = METADATA_DIR / "dataset_audit.md"
PREP_SUMMARY = METADATA_DIR / "preparation_summary.json"

FULL_OUT = PROCESSED_DIR / "processed_full_crop_model.csv"
EMBEDDED_OUT = PROCESSED_DIR / "processed_embedded_robot_model.csv"
CALIBRATION_OUT = PROCESSED_DIR / "processed_sensor_calibration.csv"
SYNTHETIC_OUT = SYNTHETIC_DIR / "embedded_catalog_synthetic.csv"

CANONICAL_ALIASES = {
    "ph": ["ph", "p_h", "soil_ph"],
    "temperature": ["temperature", "temp", "air_temperature", "soil_temperature", "soil_temp"],
    "humidity": ["humidity", "air_humidity", "relative_humidity", "rh"],
    "soil_moisture": ["soil_moisture", "moisture", "soilhumidity", "soil_humidity", "water_content", "vwc"],
    "ec": ["ec", "salinity", "conductivity", "electrical_conductivity", "soil_ec"],
    "N": ["n", "nitrogen", "N"],
    "P": ["p", "phosphorus", "P"],
    "K": ["k", "potassium", "K"],
    "rainfall": ["rainfall", "rain", "precipitation", "precip"],
    "label": ["label", "crop", "culture", "target", "class"],
    "timestamp": ["timestamp", "time", "date", "datetime"],
    "location": ["location", "site", "station", "lat", "latitude", "lon", "longitude"],
}

RANGES = {
    "ph": (3.0, 10.0),
    "temperature": (-20.0, 60.0),
    "humidity": (0.0, 100.0),
    "soil_moisture": (0.0, 100.0),
    "ec": (0.0, 12.0),
    "N": (0.0, 300.0),
    "P": (0.0, 300.0),
    "K": (0.0, 300.0),
    "rainfall": (0.0, 5000.0),
}

CROP_NAME_MAP = {
    "wheat": "Blé",
    "tomato": "Tomate",
    "onion": "Oignon",
    "carrot": "Carotte",
    "potato": "Pomme de terre",
    "barley": "Orge",
    "sugarbeet": "Betterave à sucre",
    "sugar beet": "Betterave à sucre",
    "olive": "Olivier",
    "grape": "Vigne",
    "grapes": "Vigne",
    "watermelon": "Pastèque",
}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _column_map(columns: Iterable[str]) -> dict[str, str]:
    normalized = {_norm(c): c for c in columns}
    out: dict[str, str] = {}
    for canonical, aliases in CANONICAL_ALIASES.items():
        for alias in aliases:
            n = _norm(alias)
            if n in normalized:
                out[canonical] = normalized[n]
                break
    return out


def _csv_files() -> list[Path]:
    roots = [REAL_DIR, RAW_DIR, EXTERNAL_DIR, SYNTHETIC_DIR, DATA_DIR]
    seen = set()
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in list(root.rglob("*.csv")) + list(root.rglob("*.xls")):
            if path in seen or "processed" in path.parts:
                continue
            seen.add(path)
            files.append(path)
    legacy = Path(__file__).resolve().parent / "data" / "final_dataset.csv"
    if legacy.exists() and legacy not in seen:
        files.append(legacy)
    return sorted(files)


def audit_dataset(path: Path) -> dict:
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return {"path": str(path), "status": "failed", "error": str(exc)}
    cmap = _column_map(df.columns)
    missing = df.isna().sum().to_dict()
    useful = sorted(cmap.keys())
    outliers = {}
    for key, (lo, hi) in RANGES.items():
        col = cmap.get(key)
        if not col:
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        outliers[key] = int(((vals < lo) | (vals > hi)).sum())
    return {
        "path": str(path),
        "status": "audited",
        "rows": int(len(df)),
        "columns": list(map(str, df.columns)),
        "detected_variables": useful,
        "canonical_column_map": cmap,
        "missing_values": {str(k): int(v) for k, v in missing.items()},
        "out_of_range_counts": outliers,
        "unit_notes": _unit_notes(cmap),
    }


def _unit_notes(cmap: dict[str, str]) -> dict[str, str]:
    notes = {}
    for key in cmap:
        if key in ("humidity", "soil_moisture"):
            notes[key] = "Assumed percent unless dataset documentation says otherwise."
        elif key == "temperature":
            notes[key] = "Assumed degrees Celsius."
        elif key == "ec":
            notes[key] = "Assumed mS/cm; verify source documentation."
        elif key == "rainfall":
            notes[key] = "Assumed mm."
    return notes


def write_audit(reports: list[dict]) -> None:
    write_json(AUDIT_JSON, {"generated_at": now_iso(), "datasets": reports})
    lines = ["# Dataset audit", "", f"Generated: {now_iso()}", ""]
    for r in reports:
        lines.append(f"## {r.get('path')}")
        if r.get("status") != "audited":
            lines.append(f"- status: {r.get('status')} ({r.get('error')})")
            lines.append("")
            continue
        lines.extend([
            f"- rows: {r['rows']}",
            f"- columns: {', '.join(r['columns'])}",
            f"- detected variables: {', '.join(r['detected_variables']) or 'none'}",
            f"- missing values: `{json.dumps(r['missing_values'], ensure_ascii=False)}`",
            f"- out-of-range counts: `{json.dumps(r['out_of_range_counts'], ensure_ascii=False)}`",
            "",
        ])
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def _standardize_crop_recommendation(path: Path) -> pd.DataFrame | None:
    df = pd.read_csv(path)
    cmap = _column_map(df.columns)
    if not set(FULL_FEATURES + ["label"]).issubset(cmap.keys()):
        return None
    out = pd.DataFrame()
    for feature in FULL_FEATURES:
        out[feature] = pd.to_numeric(df[cmap[feature]], errors="coerce")
    out["label"] = df[cmap["label"]].astype(str).str.strip()
    out["source_dataset"] = str(path)
    out = out.dropna(subset=FULL_FEATURES + ["label"])
    return out


def _catalog_synthetic(samples_per_crop: int = 300, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for crop, profile in CROP_CATALOG.items():
        for _ in range(samples_per_crop):
            rows.append({
                "temperature": round(float(rng.uniform(*profile.temperature) + rng.normal(0, 0.8)), 2),
                "humidity": round(float(rng.uniform(*profile.humidity) + rng.normal(0, 2.0)), 2),
                "ph": round(float(rng.uniform(*profile.ph) + rng.normal(0, 0.08)), 2),
                "ec": round(float(rng.uniform(*profile.ec) + rng.normal(0, 0.08)), 3),
                "label": crop,
                "ec_source": "synthetic_catalog",
                "source_dataset": "ml_model.rules.crop_catalog",
            })
    out = pd.DataFrame(rows)
    out["humidity"] = out["humidity"].clip(0, 100)
    out["ph"] = out["ph"].clip(3, 10)
    out["temperature"] = out["temperature"].clip(-5, 55)
    out["ec"] = out["ec"].clip(0, 12)
    return out


def _embedded_from_full(full: pd.DataFrame) -> pd.DataFrame:
    """Build the robot ML table from the real CSV without non-measured columns.

    The robot does not measure N/P/K/rainfall. The public Crop Recommendation
    CSV also does not contain measured EC, so EC is deliberately not estimated
    here. EC remains available at inference time for rules/alerts only.
    """
    if full.empty:
        return pd.DataFrame(columns=["temperature", "humidity", "ph", "label", "ec_source", "source_dataset"])
    out = full[["temperature", "humidity", "ph", "label", "source_dataset"]].copy()
    out["ec_source"] = "not_used_by_ml_missing_in_real_csv"
    return out


def _sensor_calibration_from(path: Path) -> pd.DataFrame | None:
    df = pd.read_csv(path)
    cmap = _column_map(df.columns)
    keys = [k for k in ["soil_moisture", "temperature", "humidity", "timestamp", "location"] if k in cmap]
    if not any(k in cmap for k in ["soil_moisture", "temperature", "humidity"]):
        return None
    out = pd.DataFrame()
    for key in keys:
        out[key] = df[cmap[key]]
    out["source_dataset"] = str(path)
    return out


def prepare() -> dict:
    ensure_dirs()
    files = _csv_files()
    reports = [audit_dataset(p) for p in files]
    write_audit(reports)

    full_frames = []
    calibration_frames = []
    for path in files:
        try:
            full = _standardize_crop_recommendation(path)
            if full is not None:
                full_frames.append(full)
            calib = _sensor_calibration_from(path)
            if calib is not None:
                calibration_frames.append(calib)
        except Exception:
            continue

    summary = {"generated_at": now_iso(), "files_seen": [str(p) for p in files]}
    full_df = pd.concat(full_frames, ignore_index=True).drop_duplicates() if full_frames else pd.DataFrame(columns=FULL_FEATURES + ["label", "source_dataset"])
    # Always write the processed table, even when empty, so downstream steps
    # can report "not enough rows" instead of a missing file.
    full_df.to_csv(FULL_OUT, index=False)
    summary["full_model"] = {"path": str(FULL_OUT), "rows": int(len(full_df)), "features": FULL_FEATURES}

    synthetic = _catalog_synthetic()
    synthetic.to_csv(SYNTHETIC_OUT, index=False)
    # Production ML uses the real CSV with only robot-measured columns that are
    # actually present in that CSV. We do not fabricate EC for this model.
    embedded = _embedded_from_full(full_df)
    if embedded.empty:
        # Fallback for offline/demo training only: catalog synthetic data includes
        # EC, but the ML feature list still ignores EC. Rules keep using EC.
        embedded = synthetic[["temperature", "humidity", "ph", "label", "ec_source", "source_dataset"]].copy()
    embedded = embedded.dropna(subset=["temperature", "humidity", "ph", "label"])
    embedded.to_csv(EMBEDDED_OUT, index=False)
    summary["embedded_model"] = {
        "path": str(EMBEDDED_OUT),
        "rows": int(len(embedded)),
        "features": ["temperature", "humidity", "ph"],
        "ec_source_counts": embedded["ec_source"].value_counts().to_dict() if "ec_source" in embedded else {},
        "note": "N/P/K/rainfall removed. EC is not estimated from the real CSV; EC is used by rules/alerts at inference time.",
    }

    calibration = pd.concat(calibration_frames, ignore_index=True).drop_duplicates() if calibration_frames else pd.DataFrame()
    if not calibration.empty:
        calibration.to_csv(CALIBRATION_OUT, index=False)
    summary["sensor_calibration"] = {"path": str(CALIBRATION_OUT), "rows": int(len(calibration))}
    write_json(PREP_SUMMARY, summary)
    print(f"[prepare] audit -> {AUDIT_JSON}")
    print(f"[prepare] full rows={len(full_df)} -> {FULL_OUT}")
    print(f"[prepare] embedded rows={len(embedded)} -> {EMBEDDED_OUT}")
    print(f"[prepare] calibration rows={len(calibration)} -> {CALIBRATION_OUT}")
    return summary


if __name__ == "__main__":
    prepare()
