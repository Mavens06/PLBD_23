"""
data_preparation.py
-------------------
Analyse les datasets CSV disponibles, sélectionne les plus pertinents pour
la recommandation de cultures sur 4 capteurs (humidité, pH, EC, température),
harmonise les colonnes, nettoie les données puis fusionne le tout.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from data_loader import generate_dataset

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR / "data" / "final_dataset.csv"

COLUMN_ALIASES = {
    "temperature": {"temperature", "temp", "temperature_c"},
    "humidity": {"humidity", "humidite", "humidity_pct"},
    "ph": {"ph", "soil_ph"},
    "rainfall": {"rainfall", "rain", "precipitation", "rainfall_mm"},
    "label": {"label", "crop", "crop_label", "class", "target"},
    "salinity": {"salinity", "ec", "electrical_conductivity"},
}

REQUIRED_COLS = {"temperature", "humidity", "ph", "rainfall", "label"}
OPTIONAL_COLS = ["salinity"]
DROP_COLS = {"N", "P", "K", "n", "p", "k", "nitrogen", "phosphorus", "phosphore", "potassium"}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _find_available_csvs() -> List[Path]:
    search_dirs = [
        SCRIPT_DIR / "data",
        SCRIPT_DIR,
        SCRIPT_DIR.parent / "dataset",
        SCRIPT_DIR.parent / "data",
    ]
    files: List[Path] = []
    seen = set()
    for directory in search_dirs:
        if not directory.exists():
            continue
        for path in directory.rglob("*.csv"):
            if path.resolve() == OUTPUT_PATH.resolve():
                continue
            if path.resolve() in seen:
                continue
            seen.add(path.resolve())
            files.append(path)
    return sorted(files)


def _rename_to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: Dict[str, str] = {}
    for col in df.columns:
        ncol = _norm(col)
        for canonical, aliases in COLUMN_ALIASES.items():
            if ncol in aliases and canonical not in rename_map.values():
                rename_map[col] = canonical
                break
    return df.rename(columns=rename_map)


def _clean_selected(df: pd.DataFrame) -> pd.DataFrame:
    keep_cols = ["temperature", "humidity", "ph", "rainfall", "label"] + [
        c for c in OPTIONAL_COLS if c in df.columns
    ]
    data = df[keep_cols].copy()

    for col in keep_cols:
        if col == "label":
            label_series = data[col].astype("string").str.strip()
            invalid_labels = {"", "nan", "none", "null"}
            data[col] = label_series.mask(
                label_series.isna() | label_series.str.lower().isin(invalid_labels)
            )
        else:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna(subset=["label"])
    for col in [c for c in keep_cols if c != "label"]:
        if data[col].isna().any():
            data[col] = data[col].fillna(data[col].median())
    return data


def create_final_dataset(output_path: str | os.PathLike = OUTPUT_PATH) -> Tuple[pd.DataFrame, dict]:
    csv_files = _find_available_csvs()
    if not csv_files:
        generated_path = SCRIPT_DIR / "moroccan_crop_data.csv"
        generate_dataset(output_path=str(generated_path))
        csv_files = [generated_path]

    selected_frames: List[pd.DataFrame] = []
    analysis = {"selected": [], "skipped": []}

    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path)
        except Exception as exc:
            analysis["skipped"].append({"file": str(csv_path), "reason": f"unreadable: {exc}"})
            continue

        df = _rename_to_canonical(df)
        df = df.drop(columns=[c for c in DROP_COLS if c in df.columns], errors="ignore")

        missing = REQUIRED_COLS - set(df.columns)
        if missing:
            analysis["skipped"].append(
                {"file": str(csv_path), "reason": f"missing required columns: {sorted(missing)}"}
            )
            continue

        cleaned = _clean_selected(df)
        selected_frames.append(cleaned)
        analysis["selected"].append(
            {"file": str(csv_path), "rows": cleaned.shape[0], "columns": list(cleaned.columns)}
        )

    if not selected_frames:
        raise RuntimeError("Aucun dataset pertinent trouvé pour la fusion.")

    merged = pd.concat(selected_frames, ignore_index=True)
    before_dedup = merged.shape[0]
    merged = merged.drop_duplicates().reset_index(drop=True)
    after_dedup = merged.shape[0]

    ordered_cols = ["temperature", "humidity", "ph", "rainfall"] + [
        c for c in OPTIONAL_COLS if c in merged.columns
    ] + ["label"]
    merged = merged[ordered_cols]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)

    analysis["summary"] = {
        "rows_before_dedup": before_dedup,
        "rows_after_dedup": after_dedup,
        "duplicates_removed": before_dedup - after_dedup,
        "output": str(output_path),
    }
    return merged, analysis


if __name__ == "__main__":
    final_df, report = create_final_dataset()
    print("[data_preparation] Datasets sélectionnés :")
    for item in report["selected"]:
        print(f"  - {item['file']} ({item['rows']} lignes)")
    if report["skipped"]:
        print("[data_preparation] Datasets ignorés :")
        for item in report["skipped"]:
            print(f"  - {item['file']} -> {item['reason']}")
    print(
        f"[data_preparation] Dataset final: {report['summary']['rows_after_dedup']} lignes "
        f"(doublons supprimés: {report['summary']['duplicates_removed']})"
    )
    print(f"[data_preparation] Sauvegardé -> {report['summary']['output']}")
