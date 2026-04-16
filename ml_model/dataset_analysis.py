"""
Script simple d'analyse des datasets et du processus de fusion.

Utilisation :
    python ml_model/dataset_analysis.py
"""

from data_preparation import create_final_dataset


def main() -> None:
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
