"""Download or register public agricultural datasets for Agri-Botics.

The script is intentionally conservative:
- never overwrites existing files;
- handles missing Kaggle credentials without failing the pipeline;
- records all outcomes in data/metadata/sources.json.
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

try:
    from .model_registry import METADATA_DIR, RAW_DIR, REAL_DIR, EXTERNAL_DIR, ensure_dirs, now_iso, read_json, write_json
except ImportError:
    from model_registry import METADATA_DIR, RAW_DIR, REAL_DIR, EXTERNAL_DIR, ensure_dirs, now_iso, read_json, write_json

SOURCES_PATH = METADATA_DIR / "sources.json"

CROP_REAL = REAL_DIR / "crop_recommendation.csv"
CROP_RAW = RAW_DIR / "crop_recommendation.csv"

# Public mirrors are best-effort fallbacks for environments without Kaggle.
# The file is accepted only if the expected schema is detected after download.
PUBLIC_CROP_MIRRORS = [
    "https://raw.githubusercontent.com/atharvaingle/crop-recommendation-dataset/master/Crop_recommendation.csv",
    "https://raw.githubusercontent.com/siddharthss/crop-recommendation-dataset/master/Crop_recommendation.csv",
]

EXPECTED_CROP_COLS = {"N", "P", "K", "temperature", "humidity", "ph", "rainfall", "label"}


def _columns(path: Path) -> list[str]:
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            return next(csv.reader(f))
    except Exception:
        return []


def _record(records: list[dict], name: str, source: str, path: Path | None, status: str, message: str = "") -> None:
    records.append({
        "name": name,
        "source": source,
        "downloaded_at": now_iso(),
        "local_path": str(path) if path else None,
        "columns_detected": _columns(path) if path and path.exists() else [],
        "status": status,
        "message": message,
    })


def _has_kaggle_credentials() -> bool:
    return Path.home().joinpath(".kaggle", "kaggle.json").exists() or bool(os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"))


def _try_kaggle(records: list[dict]) -> bool:
    if CROP_REAL.exists():
        _record(records, "Crop Recommendation Dataset", "manual:data/real/crop_recommendation.csv", CROP_REAL, "skipped", "Existing file preserved.")
        return True
    if not _has_kaggle_credentials():
        _record(
            records,
            "Crop Recommendation Dataset",
            "kaggle:atharvaingle/crop-recommendation-dataset",
            CROP_REAL,
            "manual_required",
            "Place kaggle.json dans ~/.kaggle/kaggle.json ou télécharge manuellement crop_recommendation.csv dans data/real/.",
        )
        return False
    if shutil.which("kaggle") is None:
        _record(records, "Crop Recommendation Dataset", "kaggle:atharvaingle/crop-recommendation-dataset", CROP_REAL, "manual_required", "Kaggle credentials found but kaggle CLI is not installed.")
        return False
    try:
        subprocess.run(
            ["kaggle", "datasets", "download", "-d", "atharvaingle/crop-recommendation-dataset", "-p", str(RAW_DIR), "--unzip"],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as exc:
        _record(records, "Crop Recommendation Dataset", "kaggle:atharvaingle/crop-recommendation-dataset", CROP_REAL, "failed", str(exc))
        return False
    candidates = list(RAW_DIR.glob("*Crop_recommendation*.csv")) + list(RAW_DIR.glob("*crop*.csv"))
    for candidate in candidates:
        if EXPECTED_CROP_COLS.issubset(set(_columns(candidate))):
            if not CROP_REAL.exists():
                shutil.copy2(candidate, CROP_REAL)
            _record(records, "Crop Recommendation Dataset", "kaggle:atharvaingle/crop-recommendation-dataset", CROP_REAL, "downloaded")
            return True
    _record(records, "Crop Recommendation Dataset", "kaggle:atharvaingle/crop-recommendation-dataset", CROP_REAL, "failed", "Downloaded files did not match expected schema.")
    return False


def _try_public_mirror(records: list[dict]) -> bool:
    if CROP_REAL.exists():
        return True
    for url in PUBLIC_CROP_MIRRORS:
        if CROP_RAW.exists():
            _record(records, "Crop Recommendation Dataset mirror", url, CROP_RAW, "skipped", "Existing raw file preserved.")
            break
        try:
            with urlopen(url, timeout=20) as r:
                data = r.read()
            if len(data) > 20_000_000:
                _record(records, "Crop Recommendation Dataset mirror", url, CROP_RAW, "failed", "File too large for conservative downloader.")
                continue
            CROP_RAW.write_bytes(data)
            cols = set(_columns(CROP_RAW))
            if EXPECTED_CROP_COLS.issubset(cols):
                shutil.copy2(CROP_RAW, CROP_REAL)
                _record(records, "Crop Recommendation Dataset mirror", url, CROP_REAL, "downloaded")
                return True
            CROP_RAW.unlink(missing_ok=True)
            _record(records, "Crop Recommendation Dataset mirror", url, CROP_RAW, "failed", "Schema mismatch; file discarded.")
        except (URLError, HTTPError, TimeoutError, OSError) as exc:
            _record(records, "Crop Recommendation Dataset mirror", url, CROP_RAW, "failed", str(exc))
    return CROP_REAL.exists()


def main() -> int:
    ensure_dirs()
    records = read_json(SOURCES_PATH, [])
    if not isinstance(records, list):
        records = []

    crop_ok = _try_kaggle(records)
    if not crop_ok:
        _try_public_mirror(records)

    manual_sources = [
        ("FAO EcoCrop / equivalent agronomic ranges", "manual:place CSV in data/external/", EXTERNAL_DIR, "manual_required", "Use to validate or enrich crop_catalog.py; no automatic safe direct CSV URL configured."),
        ("WHIN/Purdue-style soil sensor dataset", "manual:place CSV in data/external/", EXTERNAL_DIR, "manual_required", "Use for sensor calibration only when crop label is absent."),
        ("Open Soil Data / OpenLandMap / WoSIS extracts", "manual:place CSV in data/external/", EXTERNAL_DIR, "manual_required", "Prepared as secondary sources; not forced into crop classification."),
    ]
    for name, source, path, status, msg in manual_sources:
        _record(records, name, source, path, status, msg)

    write_json(SOURCES_PATH, records)
    print(f"[download] metadata written -> {SOURCES_PATH}")
    if not CROP_REAL.exists():
        print("[download] Place kaggle.json dans ~/.kaggle/kaggle.json ou télécharge manuellement crop_recommendation.csv dans data/real/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
