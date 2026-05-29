"""
data_preparation.py
-------------------
Génère ou (re)génère le dataset d'entraînement final pour Agribotics.

La source de vérité agronomique est `ml_model/rules/crop_catalog.py`.
Le dataset est entièrement synthétique et calibré sur les 4 variables du
capteur 4-en-1 RS485 :  pH, humidité, température, EC.

Aucune autre variable n'est conservée :
  ✗ N, P, K        — hors périmètre capteur
  ✗ rainfall       — hors périmètre capteur

Si un CSV `final_dataset.csv` existe déjà avec des colonnes hors-périmètre
(ex. anciens datasets), il est ignoré et regénéré.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Tuple

import pandas as pd

from data_loader import FEATURE_ORDER, generate_dataset


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_DIR / "data" / "final_dataset.csv"


def create_final_dataset(
    output_path: str | os.PathLike = OUTPUT_PATH,
    samples_per_crop: int = 1000,
    seed: int = 42,
) -> Tuple[pd.DataFrame, dict]:
    """
    (Re)génère le dataset final synthétique.

    Returns
    -------
    (df, report) — df pandas + dict avec stats utiles.
    """
    output_path = Path(output_path)
    df = generate_dataset(
        samples_per_crop=samples_per_crop,
        seed=seed,
        output_path=output_path,
    )

    # Sanity check : aucune colonne hors-périmètre ne doit subsister.
    forbidden = {"N", "P", "K", "rainfall", "n", "p", "k", "Rainfall"}
    leaks = sorted(set(df.columns) & forbidden)
    if leaks:
        raise RuntimeError(f"Colonnes hors-périmètre détectées : {leaks}")

    expected_cols = FEATURE_ORDER + ["label"]
    if list(df.columns) != expected_cols:
        raise RuntimeError(
            f"Ordre/colonnes inattendus : {list(df.columns)} != {expected_cols}"
        )

    counts = df["label"].value_counts().sort_index().to_dict()
    report = {
        "rows": len(df),
        "classes": int(df["label"].nunique()),
        "samples_per_class": counts,
        "features": FEATURE_ORDER,
        "output": str(output_path),
    }
    return df, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Préparation du dataset final Agribotics")
    parser.add_argument("-n", "--samples", type=int, default=1000,
                        help="Échantillons par culture (défaut 1000)")
    parser.add_argument("-o", "--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    df, report = create_final_dataset(
        output_path=args.output, samples_per_crop=args.samples,
    )
    print("[data_preparation] Dataset final :")
    print(f"  • {report['rows']} lignes")
    print(f"  • {report['classes']} classes (équilibré : {args.samples}/classe)")
    print(f"  • Features : {report['features']}")
    print(f"  • Distribution :")
    for crop, n in sorted(report["samples_per_class"].items()):
        print(f"      - {crop:18s} : {n}")
    print(f"  • Sauvegardé → {report['output']}")


if __name__ == "__main__":
    main()
