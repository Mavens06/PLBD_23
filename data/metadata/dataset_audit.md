# Dataset audit

Generated: 2026-06-08T16:18:32.197097+00:00

## /home/marius/Documents/Marius/PLBD/data/real/Crop_recommendation.xls
- rows: 2200
- columns: N, P, K, temperature, humidity, ph, rainfall, label
- detected variables: K, N, P, humidity, label, ph, rainfall, temperature
- missing values: `{"N": 0, "P": 0, "K": 0, "temperature": 0, "humidity": 0, "ph": 0, "rainfall": 0, "label": 0}`
- out-of-range counts: `{"ph": 0, "temperature": 0, "humidity": 0, "N": 0, "P": 0, "K": 0, "rainfall": 0}`

## /home/marius/Documents/Marius/PLBD/data/synthetic/embedded_catalog_synthetic.csv
- rows: 3000
- columns: temperature, humidity, ph, ec, label, ec_source, source_dataset
- detected variables: ec, humidity, label, ph, temperature
- missing values: `{"temperature": 0, "humidity": 0, "ph": 0, "ec": 0, "label": 0, "ec_source": 0, "source_dataset": 0}`
- out-of-range counts: `{"ph": 0, "temperature": 0, "humidity": 0, "ec": 0}`

## /home/marius/Documents/Marius/PLBD/ml_model/data/final_dataset.csv
- rows: 10000
- columns: ph, humidity, temperature, ec, label
- detected variables: ec, humidity, label, ph, temperature
- missing values: `{"ph": 0, "humidity": 0, "temperature": 0, "ec": 0, "label": 0}`
- out-of-range counts: `{"ph": 0, "temperature": 0, "humidity": 0, "ec": 0}`
