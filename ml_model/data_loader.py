# =============================================================================
# data_loader.py
# Chargement du dataset public de recommandation de cultures agricoles.
# Le dataset contient les colonnes : N, P, K, temperature, humidity, ph,
# rainfall et label (nom de la culture recommandée).
# =============================================================================

import pandas as pd
import requests
import io
import os

# URL publique du dataset standard de recommandation de cultures
DATASET_URL = (
    "https://raw.githubusercontent.com/Surya-Sankar/"
    "Crop-Recommendation-System/master/Crop_recommendation.csv"
)

# Chemin local de cache pour éviter un téléchargement répété
CACHE_PATH = os.path.join(os.path.dirname(__file__), "Crop_recommendation.csv")


def telecharger_dataset(url: str = DATASET_URL, cache: str = CACHE_PATH) -> pd.DataFrame:
    """
    Télécharge le dataset depuis une URL publique et le met en cache localement.

    Paramètres
    ----------
    url   : URL du fichier CSV hébergé en ligne.
    cache : Chemin local où sauvegarder le fichier téléchargé.

    Retourne
    --------
    pd.DataFrame : Le dataset complet sous forme de DataFrame pandas.
    """
    # Si le fichier est déjà en cache, on le charge directement
    if os.path.exists(cache):
        print(f"[INFO] Chargement depuis le cache local : {cache}")
        return pd.read_csv(cache)

    print(f"[INFO] Téléchargement du dataset depuis : {url}")
    reponse = requests.get(url, timeout=30)
    reponse.raise_for_status()  # Lève une exception si le téléchargement échoue

    # Sauvegarde locale pour les prochaines exécutions
    with open(cache, "wb") as f:
        f.write(reponse.content)
    print(f"[INFO] Dataset sauvegardé localement dans : {cache}")

    df = pd.read_csv(io.BytesIO(reponse.content))
    return df


def charger_donnees(url: str = DATASET_URL) -> pd.DataFrame:
    """
    Point d'entrée principal pour charger le dataset de cultures.
    Affiche un résumé rapide du dataset pour vérification.

    Retourne
    --------
    pd.DataFrame : Le dataset prêt à l'emploi.
    """
    df = telecharger_dataset(url)

    print("\n[INFO] Aperçu du dataset :")
    print(df.head())
    print(f"\n[INFO] Dimensions : {df.shape[0]} lignes x {df.shape[1]} colonnes")
    print(f"[INFO] Colonnes    : {list(df.columns)}")
    print(f"[INFO] Cultures uniques ({df['label'].nunique()}) : {sorted(df['label'].unique())}")
    print(f"[INFO] Valeurs manquantes :\n{df.isnull().sum()}")

    return df


# --- Exécution directe pour test rapide ---
if __name__ == "__main__":
    donnees = charger_donnees()
    print("\n[OK] Dataset chargé avec succès.")
