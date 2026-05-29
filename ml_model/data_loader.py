"""
data_loader.py
--------------
Génère un dataset synthétique étiqueté pour la classification de culture
à partir des **4 variables exactes** du capteur 4-en-1 RS485 :

  • pH du sol
  • humidité du sol (%)
  • température du sol (°C)
  • conductivité électrique / salinité (EC, mS/cm)

Aucune autre variable n'est générée :
  ✗ pas de N, P, K   (hors périmètre capteur)
  ✗ pas de rainfall  (hors périmètre capteur)

Les plages agronomiques de chaque culture proviennent de
`ml_model/rules/crop_catalog.py` — c'est la seule vérité terrain partagée
entre le moteur de règles et l'entraînement ML. Toute évolution des plages
se fait dans crop_catalog.py et se propage automatiquement ici.

Génération :
  • Chaque culture produit N échantillons (défaut 1000 → 10 000 lignes total).
  • Pour chaque variable : 85 % au cœur de la plage optimale, 15 % en bordure
    (pour rester réaliste face aux mesures capteur en limite de plage).
    Les tirages franchement hors plage sont désactivés (bruit d'étiquetage).
  • Bruit gaussien proportionnel à la largeur de la plage.
  • Mélange final pour éviter tout biais d'ordre.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from rules.crop_catalog import CROP_CATALOG, CropProfile, all_crops


SEED = 42
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "final_dataset.csv"

# Ordre canonique des features partagé avec preprocess.py et predict.py.
FEATURE_ORDER = ["ph", "humidity", "temperature", "ec"]


def _sample_in_range(
    lo: float,
    hi: float,
    n: int,
    rng: np.random.Generator,
    core_frac: float = 0.85,
    border_frac: float = 0.15,
    out_frac: float = 0.0,
) -> np.ndarray:
    """
    Tirage d'une variable autour d'une plage agronomique [lo, hi].

    Construction d'un mélange :
      • core_frac (85 % par défaut) : uniforme strictement dans [lo, hi]
        + petit bruit gaussien (sigma = width * 0.05).
      • border_frac (15 %) : tirages dans une fenêtre élargie autour des
        bornes (±width * 0.10) pour rester réaliste face aux mesures
        capteur en limite de plage.
      • out_frac (0 % par défaut) : tirages plus loin (jusqu'à width * 0.40
        hors plage). DÉSACTIVÉ — ces échantillons, étiquetés avec la culture
        d'origine mais tombant dans le cœur d'une autre culture, sont du
        bruit d'étiquetage pur : ils dégradent top-1 et top-3 sans rien
        apprendre d'utile (cf. crop_catalog : 92 % de plages communes
        Carotte/Pomme de terre, 84 % Blé/Orge).
    """
    width = max(hi - lo, 1e-6)
    n_core = int(round(n * core_frac))
    n_border = int(round(n * border_frac))
    n_out = n - n_core - n_border

    # cœur : uniforme dans [lo, hi] + léger bruit gaussien
    core = rng.uniform(lo, hi, n_core) + rng.normal(0.0, width * 0.05, n_core)

    # bordure : autour des deux bornes (mélange ±)
    half = n_border // 2
    border_lo = rng.normal(lo, width * 0.10, half)
    border_hi = rng.normal(hi, width * 0.10, n_border - half)
    border = np.concatenate([border_lo, border_hi])

    # hors plage : éloignement modéré (désactivé par défaut, out_frac=0.0).
    # Gardé derrière `if n_out` pour ne pas consommer de tirages RNG inutiles
    # et préserver la reproductibilité cœur/bordure (cf. revue de code, #10).
    parts = [core, border]
    if n_out:
        side = rng.choice([-1.0, 1.0], n_out)
        outside = np.where(
            side < 0,
            lo - rng.uniform(width * 0.05, width * 0.40, n_out),
            hi + rng.uniform(width * 0.05, width * 0.40, n_out),
        )
        parts.append(outside)

    samples = np.concatenate(parts)
    rng.shuffle(samples)
    return samples


# Bornes de saisie réalistes côté capteur (saturation physique).
_PHYS_BOUNDS = {
    "ph":          (3.0, 10.0),
    "humidity":    (0.0, 100.0),
    "temperature": (-5.0, 55.0),
    "ec":          (0.0, 12.0),
}


def _clip_physical(values: np.ndarray, variable: str) -> np.ndarray:
    lo, hi = _PHYS_BOUNDS[variable]
    return np.clip(values, lo, hi)


def _generate_rows_for_crop(
    profile: CropProfile,
    n_samples: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Génère n_samples lignes synthétiques pour une culture donnée."""
    ph          = _sample_in_range(*profile.ph,          n_samples, rng)
    humidity    = _sample_in_range(*profile.humidity,    n_samples, rng)
    temperature = _sample_in_range(*profile.temperature, n_samples, rng)
    ec          = _sample_in_range(*profile.ec,          n_samples, rng)

    return pd.DataFrame({
        "ph":          np.round(_clip_physical(ph,          "ph"),          2),
        "humidity":    np.round(_clip_physical(humidity,    "humidity"),    2),
        "temperature": np.round(_clip_physical(temperature, "temperature"), 2),
        "ec":          np.round(_clip_physical(ec,          "ec"),          3),
        "label":       profile.name,
    })


def generate_dataset(
    samples_per_crop: int = 1000,
    crops: Iterable[str] | None = None,
    seed: int = SEED,
    output_path: str | os.PathLike | None = None,
) -> pd.DataFrame:
    """
    Génère le dataset synthétique complet sur les 10 cultures du catalogue V1.

    Parameters
    ----------
    samples_per_crop : int
        Nombre d'échantillons par culture (équilibré). Défaut 1000 → 10 000 lignes.
    crops : iterable de noms de cultures, optionnel
        Restriction à un sous-ensemble (défaut : toutes les cultures de CROP_CATALOG).
    seed : int
        Graine pour reproductibilité.
    output_path : str ou Path, optionnel
        Si fourni, sauvegarde en CSV.

    Returns
    -------
    pd.DataFrame de shape (samples_per_crop × n_crops, 5) avec colonnes
    ['ph', 'humidity', 'temperature', 'ec', 'label'].
    """
    names = list(crops) if crops else all_crops()
    rng = np.random.default_rng(seed)

    frames = []
    for name in names:
        profile = CROP_CATALOG[name]
        # On dérive une sous-RNG par culture pour stabilité indépendamment de l'ordre.
        crop_rng = np.random.default_rng(rng.integers(0, 2**31 - 1))
        frames.append(_generate_rows_for_crop(profile, samples_per_crop, crop_rng))

    df = pd.concat(frames, ignore_index=True)
    # Mélange global
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    # Réordonne les colonnes : features puis label
    df = df[FEATURE_ORDER + ["label"]]

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Génération du dataset synthétique Agribotics")
    parser.add_argument("-n", "--samples", type=int, default=1000,
                        help="Échantillons par culture (défaut 1000 → 10 000 lignes)")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT),
                        help="Chemin CSV de sortie")
    args = parser.parse_args()

    df = generate_dataset(samples_per_crop=args.samples, output_path=args.output)
    print(f"[data_loader] Dataset généré : {len(df)} lignes, {df['label'].nunique()} cultures")
    print(f"[data_loader] Distribution :")
    print(df["label"].value_counts().sort_index().to_string())
    print(f"[data_loader] Sauvegardé → {args.output}")


if __name__ == "__main__":
    main()
