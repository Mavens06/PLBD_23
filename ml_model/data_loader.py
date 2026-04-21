"""Generate a lightweight synthetic dataset based on 4 soil sensors."""

import os

import numpy as np
import pandas as pd

SEED = 42
np.random.seed(SEED)

CROPS = {
    'blé': {'temperature': (10, 24), 'humidity': (40, 65), 'ph': (6.0, 7.5), 'rainfall': (250, 500), 'salinity': (0.4, 2.4), 'n_samples': 180},
    'orge': {'temperature': (8, 22), 'humidity': (35, 60), 'ph': (6.0, 8.0), 'rainfall': (180, 420), 'salinity': (0.5, 3.0), 'n_samples': 170},
    'maïs': {'temperature': (18, 32), 'humidity': (50, 75), 'ph': (5.8, 7.0), 'rainfall': (350, 700), 'salinity': (0.3, 2.2), 'n_samples': 150},
    'tomate': {'temperature': (18, 30), 'humidity': (55, 75), 'ph': (6.0, 6.8), 'rainfall': (300, 600), 'salinity': (0.3, 2.5), 'n_samples': 150},
    'pomme de terre': {'temperature': (12, 24), 'humidity': (60, 80), 'ph': (5.2, 6.5), 'rainfall': (300, 650), 'salinity': (0.2, 1.8), 'n_samples': 140},
    'oignon': {'temperature': (14, 28), 'humidity': (50, 70), 'ph': (6.0, 7.0), 'rainfall': (250, 450), 'salinity': (0.4, 2.2), 'n_samples': 140},
    'olivier': {'temperature': (14, 34), 'humidity': (30, 55), 'ph': (6.5, 8.5), 'rainfall': (120, 500), 'salinity': (1.0, 4.0), 'n_samples': 170},
    'agrumes': {'temperature': (14, 30), 'humidity': (55, 75), 'ph': (5.5, 7.5), 'rainfall': (300, 700), 'salinity': (0.5, 2.6), 'n_samples': 160},
    'luzerne': {'temperature': (12, 30), 'humidity': (45, 70), 'ph': (6.2, 7.8), 'rainfall': (250, 550), 'salinity': (0.5, 2.8), 'n_samples': 150},
    'pois chiche': {'temperature': (15, 28), 'humidity': (35, 60), 'ph': (6.0, 8.0), 'rainfall': (180, 420), 'salinity': (0.3, 3.0), 'n_samples': 140},
}


def _generate_crop_rows(label: str, params: dict) -> pd.DataFrame:
    n = params['n_samples']
    rng = np.random.default_rng(SEED + abs(hash(label)) % 10000)

    def uniform(lo, hi):
        return rng.uniform(lo, hi, n)

    return pd.DataFrame(
        {
            'temperature': np.round(uniform(*params['temperature']), 1),
            'humidity': np.round(uniform(*params['humidity']), 1),
            'ph': np.round(uniform(*params['ph']), 2),
            'rainfall': np.round(uniform(*params['rainfall']), 1),
            'salinity': np.round(uniform(*params['salinity']), 2),
            'label': label,
        }
    )


def generate_dataset(output_path: str | None = None) -> pd.DataFrame:
    frames = [_generate_crop_rows(label, params) for label, params in CROPS.items()]
    df = pd.concat(frames, ignore_index=True).sample(frac=1, random_state=SEED).reset_index(drop=True)

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)

    return df


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'moroccan_crop_data.csv')
    generate_dataset(output_path=csv_path)
