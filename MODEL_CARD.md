# Agri-Botics Model Card

Generated: 2026-06-08T16:18:54.635871+00:00

## Purpose

Agri-Botics uses crop recommendation models as decision support. The robot-facing recommendation never requires N/P/K/rainfall; it uses only temperature, humidity, pH, and EC, then applies the agronomic rules engine as a guardrail. The default **production** model (`ml_model/best_model.pkl`) classifies the 10 Moroccan target crops from these 4 variables. The public-data models described below (embedded, full) are kept for research/audit only and are **disabled by default**.

## Datasets

- Crop Recommendation Dataset: manual_required (kaggle:atharvaingle/crop-recommendation-dataset) -> /home/marius/Documents/Marius/PLBD/data/real/crop_recommendation.csv
- Crop Recommendation Dataset mirror: failed (https://raw.githubusercontent.com/atharvaingle/crop-recommendation-dataset/master/Crop_recommendation.csv) -> /home/marius/Documents/Marius/PLBD/data/raw/crop_recommendation.csv
- Crop Recommendation Dataset mirror: failed (https://raw.githubusercontent.com/siddharthss/crop-recommendation-dataset/master/Crop_recommendation.csv) -> /home/marius/Documents/Marius/PLBD/data/raw/crop_recommendation.csv
- FAO EcoCrop / equivalent agronomic ranges: manual_required (manual:place CSV in data/external/) -> /home/marius/Documents/Marius/PLBD/data/external
- WHIN/Purdue-style soil sensor dataset: manual_required (manual:place CSV in data/external/) -> /home/marius/Documents/Marius/PLBD/data/external
- Open Soil Data / OpenLandMap / WoSIS extracts: manual_required (manual:place CSV in data/external/) -> /home/marius/Documents/Marius/PLBD/data/external

## Processed Tables

- `data/processed/processed_full_crop_model.csv`: audited only. It contains N/P/K/rainfall and is not used by the robot model.
- `data/processed/processed_embedded_robot_model.csv`: **research** table built from the public Kaggle CSV after dropping N/P/K/rainfall. Features: temperature, humidity, pH. Used only by the experimental embedded model (disabled by default), not by the production model.
- `data/processed/processed_sensor_calibration.csv`: optional sensor calibration table. It is not used for crop classification unless a crop label is present and meaningful.

## Models

### Production model (default) — `ml_model/best_model.pkl`

**This is the robot-facing model served by `ml_model/predict.py`.** Features: `pH`, `humidity`, `temperature`, `EC` — the 4 RS485 sensor variables. Classes: the 10 Moroccan target crops (Blé, Tomate, Oignon, Carotte, Pomme de terre, Orge, Betterave à sucre, Olivier, Vigne, Pastèque). Trained on a synthetic dataset calibrated on `ml_model/rules/crop_catalog.py`. The rules engine is applied as an agronomic guardrail. If the model file is absent, `predict.py` falls back to the rules engine (no exception).

### Embedded experimental model — `ml_model/models/embedded_model.pkl` (research only)

Features: `temperature`, `humidity`, `ph` (3 features, **no EC**). Classes: the public Kaggle crop dataset (tropical crops such as rice, coffee, jute — **outside the project's 10-crop perimeter**). **Disabled by default**: `predict.py` uses it only when `USE_EMBEDDED_MODEL=1`. Recommending tropical crops for Moroccan soil and ignoring EC would break agronomic coherence, so this model is kept only to document the public-data baseline.

### Full experimental model — `ml_model/models/full_model.pkl` (disabled)

Features include `N`, `P`, `K` and `rainfall`, which the robot does not measure. Kept for audit/research only; never a production model.

## Metrics

- **Production model** (`best_model.pkl`, 4 features incl. EC, 10 Moroccan crops): top-3 ≈ 0.91, top-1 ≈ 0.57 on the synthetic catalog dataset. Top-3 is the reference metric (the API exposes a top-3). See CLAUDE.md « Performances » for the full table.
- embedded_model (research, 3 features, Kaggle crops): accuracy=0.725, f1_macro=0.7217, rows_evaluated=440.
- full_model: unavailable (disabled: N/P/K/rainfall are not measured by the robot).

## Role of rules

The ML model proposes a top-3. The rules engine checks pH, humidity, temperature, and EC against crop ranges. Inconsistent high-confidence ML suggestions are penalized or flagged instead of blindly accepted.

## Current limitations

- Public crop datasets contain N/P/K/rainfall but no measured EC. Those non-measured columns are dropped for the robot model; EC is handled by rules until real EC-labeled data exists.
- Sensor calibration datasets without crop labels must not be used directly for crop classification.
- Metrics on synthetic/catalog data are not equivalent to field validation.

## Future improvements with real sensors

- Replace estimated/synthetic EC rows with measured EC from the RS485 probe.
- Persist field sessions and use confirmed farmer outcomes as labels.
- Expand `crop_catalog.py` only when source ranges are documented and compatible with Moroccan crops.
