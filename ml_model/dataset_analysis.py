"""
Script simple d'analyse des datasets et du processus de fusion.

Utilisation :
    python ml_model/dataset_analysis.py
    python ml_model/dataset_analysis.py --dataset ml_model/data/final_dataset.csv
"""

import argparse
from pathlib import Path

import pandas as pd

from data_preparation import create_final_dataset


def _analyze_existing_dataset(dataset_path: Path):
    final_df = pd.read_csv(dataset_path)
    rows_before = final_df.shape[0]
    rows_after = final_df.drop_duplicates().shape[0]
    report = {
        "selected": [],
        "skipped": [],
        "summary": {
            "rows_before_dedup": rows_before,
            "rows_after_dedup": rows_after,
            "duplicates_removed": rows_before - rows_after,
            "output": str(dataset_path),
        },
    }
    return final_df, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse des datasets ML et fusion finale.")
    parser.add_argument("--dataset", help="Chemin d'un dataset final existant à analyser sans régénérer.")
    args = parser.parse_args()

    if args.dataset:
        final_df, report = _analyze_existing_dataset(Path(args.dataset))
    else:
        final_df, report = create_final_dataset()

    print("=== Analyse des datasets disponibles ===")
    print(f"Datasets retenus : {len(report['selected'])}")
    for ds in report["selected"]:
        print(f" - {ds['file']} | lignes retenues: {ds['rows']} | colonnes: {', '.join(ds['columns'])}")

    if report["skipped"]:
        print("\nDatasets ignorés :")
        for ds in report["skipped"]:
            print(f" - {ds['file']} | raison: {ds['reason']}")

    print("\n=== Fusion et nettoyage ===")
    summary = report["summary"]
    print(f"Lignes avant suppression des doublons : {summary['rows_before_dedup']}")
    print(f"Lignes après suppression des doublons : {summary['rows_after_dedup']}")
    print(f"Doublons supprimés : {summary['duplicates_removed']}")
    print(f"Dataset final enregistré : {summary['output']}")

    print("\nAperçu du dataset final :")
    print(final_df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
