"""
data_loader.py
--------------
Génère un dataset synthétique réaliste pour les cultures agricoles marocaines.
Les plages de valeurs sont calibrées sur le climat et les sols du Maroc
(Souss, Gharb, Tadla, Doukkala, Haouz).

Cultures incluses :
  Blé (Blé tendre), Orge, Olivier, Arganier, Palmier dattier,
  Tomate, Agrumes, Menthe, Maïs, Betterave sucrière,
  Pomme de terre, Grenade, Pastèque, Pois chiche, Lentille

Colonnes générées :
  N, P, K, temperature, humidity, ph, rainfall, salinity, label
"""

import numpy as np
import pandas as pd
import os

# ── Graine aléatoire pour la reproductibilité ──────────────────────────────────
SEED = 42
np.random.seed(SEED)

# ── Définition des cultures marocaines et de leurs plages de paramètres ─────────
# Chaque entrée : (N_min, N_max, P_min, P_max, K_min, K_max,
#                  temp_min, temp_max, hum_min, hum_max,
#                  ph_min, ph_max, rain_min, rain_max,
#                  sal_min, sal_max)
CROPS = {
    "ble": {
        "label": "Blé",
        "N": (80, 140), "P": (40, 80), "K": (40, 80),
        "temperature": (10, 22), "humidity": (45, 70),
        "ph": (6.0, 7.8), "rainfall": (300, 550),
        "salinity": (0.5, 3.0),
        "n_samples": 200,
    },
    "orge": {
        "label": "Orge",
        "N": (60, 110), "P": (30, 65), "K": (30, 65),
        "temperature": (8, 20), "humidity": (40, 65),
        "ph": (6.0, 8.0), "rainfall": (200, 450),
        "salinity": (0.5, 4.0),
        "n_samples": 180,
    },
    "mais": {
        "label": "Maïs",
        "N": (100, 180), "P": (50, 90), "K": (60, 120),
        "temperature": (18, 32), "humidity": (55, 80),
        "ph": (5.8, 7.5), "rainfall": (400, 700),
        "salinity": (0.3, 2.5),
        "n_samples": 160,
    },
    "olivier": {
        "label": "Olivier",
        "N": (40, 90), "P": (20, 55), "K": (50, 100),
        "temperature": (14, 30), "humidity": (35, 65),
        "ph": (6.0, 8.3), "rainfall": (200, 600),
        "salinity": (1.0, 5.0),
        "n_samples": 200,
    },
    "arganier": {
        # Endémique du Souss-Massa : aridité, fortes chaleurs, haute tolérance à la salinité
        "label": "Arganier",
        "N": (10, 40), "P": (5, 25), "K": (10, 35),
        "temperature": (22, 38), "humidity": (20, 45),
        "ph": (7.0, 8.5), "rainfall": (80, 250),
        "salinity": (3.0, 8.0),
        "n_samples": 160,
    },
    "palmier_dattier": {
        # Régions sahariennes : Drâa, Tafilalet — hautes températures, faibles pluies
        "label": "Palmier dattier",
        "N": (30, 70), "P": (15, 45), "K": (80, 150),
        "temperature": (25, 42), "humidity": (15, 40),
        "ph": (7.0, 8.5), "rainfall": (50, 200),
        "salinity": (2.0, 10.0),
        "n_samples": 160,
    },
    "tomate": {
        "label": "Tomate",
        "N": (80, 150), "P": (60, 110), "K": (100, 180),
        "temperature": (16, 30), "humidity": (60, 85),
        "ph": (5.5, 7.0), "rainfall": (350, 600),
        "salinity": (0.3, 2.5),
        "n_samples": 180,
    },
    "agrumes": {
        # Souss, Gharb : températures douces, humidité modérée
        "label": "Agrumes",
        "N": (70, 130), "P": (40, 80), "K": (80, 140),
        "temperature": (14, 28), "humidity": (55, 80),
        "ph": (5.5, 7.0), "rainfall": (400, 800),
        "salinity": (0.5, 3.5),
        "n_samples": 180,
    },
    "menthe": {
        "label": "Menthe",
        "N": (50, 100), "P": (30, 60), "K": (40, 80),
        "temperature": (14, 26), "humidity": (60, 85),
        "ph": (6.0, 7.5), "rainfall": (300, 600),
        "salinity": (0.2, 2.0),
        "n_samples": 140,
    },
    "betterave": {
        "label": "Betterave sucrière",
        "N": (100, 160), "P": (60, 100), "K": (150, 220),
        "temperature": (12, 24), "humidity": (50, 75),
        "ph": (6.5, 8.0), "rainfall": (450, 700),
        "salinity": (1.0, 5.0),
        "n_samples": 140,
    },
    "pomme_de_terre": {
        "label": "Pomme de terre",
        "N": (80, 140), "P": (60, 100), "K": (120, 180),
        "temperature": (10, 22), "humidity": (60, 80),
        "ph": (4.8, 6.5), "rainfall": (400, 650),
        "salinity": (0.2, 1.5),
        "n_samples": 130,
    },
    "grenade": {
        "label": "Grenade",
        "N": (40, 90), "P": (25, 60), "K": (60, 110),
        "temperature": (18, 36), "humidity": (30, 60),
        "ph": (5.5, 8.0), "rainfall": (150, 500),
        "salinity": (1.0, 6.0),
        "n_samples": 120,
    },
    "pasteque": {
        "label": "Pastèque",
        "N": (50, 110), "P": (40, 80), "K": (80, 140),
        "temperature": (22, 35), "humidity": (45, 75),
        "ph": (6.0, 7.5), "rainfall": (200, 500),
        "salinity": (0.5, 3.0),
        "n_samples": 120,
    },
    "pois_chiche": {
        "label": "Pois chiche",
        "N": (10, 40), "P": (40, 80), "K": (20, 60),
        "temperature": (15, 28), "humidity": (35, 65),
        "ph": (6.0, 8.0), "rainfall": (200, 450),
        "salinity": (0.3, 3.5),
        "n_samples": 110,
    },
    "lentille": {
        "label": "Lentille",
        "N": (10, 35), "P": (30, 70), "K": (20, 50),
        "temperature": (12, 25), "humidity": (40, 65),
        "ph": (6.0, 8.0), "rainfall": (250, 450),
        "salinity": (0.3, 2.5),
        "n_samples": 120,
    },
}


def _generate_crop_rows(crop_key: str, params: dict) -> pd.DataFrame:
    """Génère des lignes synthétiques pour une culture donnée."""
    n = params["n_samples"]
    rng = np.random.default_rng(SEED + hash(crop_key) % 10000)

    def uniform(lo, hi):
        return rng.uniform(lo, hi, n)

    data = {
        "N":           np.round(uniform(*params["N"]), 1),
        "P":           np.round(uniform(*params["P"]), 1),
        "K":           np.round(uniform(*params["K"]), 1),
        "temperature": np.round(uniform(*params["temperature"]), 1),
        "humidity":    np.round(uniform(*params["humidity"]), 1),
        "ph":          np.round(uniform(*params["ph"]), 2),
        "rainfall":    np.round(uniform(*params["rainfall"]), 1),
        "salinity":    np.round(uniform(*params["salinity"]), 2),
        "label":       params["label"],
    }
    return pd.DataFrame(data)


def generate_dataset(output_path: str = None) -> pd.DataFrame:
    """
    Génère le dataset complet pour toutes les cultures marocaines,
    le mélange, puis le sauvegarde en CSV si output_path est fourni.

    Retourne le DataFrame.
    """
    frames = [_generate_crop_rows(key, params) for key, params in CROPS.items()]
    df = pd.concat(frames, ignore_index=True)

    # Mélanger les lignes pour éviter tout biais lié à l'ordre
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

    total = len(df)
    print(f"[data_loader] Dataset généré : {total} lignes, {df['label'].nunique()} cultures.")
    print(f"[data_loader] Distribution des cultures :\n{df['label'].value_counts().to_string()}\n")

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"[data_loader] Données sauvegardées → {output_path}")

    return df


if __name__ == "__main__":
    # Chemin de sortie relatif à l'emplacement de ce fichier
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "moroccan_crop_data.csv")
    df = generate_dataset(output_path=csv_path)
    print(df.head(10))
