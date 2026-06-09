# Agri-Botics data workspace

This directory separates raw public datasets, manually supplied real datasets, processed training tables, synthetic data, and metadata.

## Layout

- `raw/`: untouched files downloaded automatically when a safe public URL is available.
- `real/`: user-provided real datasets, especially `crop_recommendation.csv`.
- `external/`: secondary public sources prepared for manual import, for example EcoCrop/OpenLandMap/WoSIS exports.
- `processed/`: normalized CSV files produced by `ml_model/prepare_dataset.py`.
- `synthetic/`: generated or calibrated synthetic tables derived from `ml_model/rules/crop_catalog.py`.
- `metadata/`: source manifests, audit reports, and preparation summaries.

## Manual datasets

### Crop Recommendation Dataset

If Kaggle credentials are not configured, download the public Crop Recommendation dataset manually and place it here:

```text
data/real/crop_recommendation.csv
```

Expected columns:

```text
N, P, K, temperature, humidity, ph, rainfall, label
```

Kaggle credentials, when used, should be placed at:

```text
~/.kaggle/kaggle.json
```

### EcoCrop / agronomic ranges

FAO EcoCrop style data is useful for validating or extending `ml_model/rules/crop_catalog.py`. If available as CSV, place it in `data/external/` and rerun:

```bash
python ml_model/prepare_dataset.py
```

### Soil sensor / soil property datasets

WHIN/Purdue-style sensor datasets, Open Soil Data, OpenLandMap, or WoSIS extracts should be placed in `data/external/` or `data/raw/`. If they do not contain a crop label, they are audited and may feed `processed_sensor_calibration.csv`, but they are not used for crop classification.
