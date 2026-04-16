"""
chatbot_llm.py – Couche conversationnelle d'AgriBot propulsée par un LLM OpenAI.

Note d'architecture :
  La Raspberry Pi effectue tout le travail lourd :
    • Lecture des capteurs physiques (pH, humidité, température, pluviométrie, salinité)
    • Exécution du modèle Scikit-Learn local (best_model.pkl) pour produire une
      recommandation de culture (ml_prediction).

  Ce module n'effectue AUCUN apprentissage automatique ni traitement capteur.
  Sa seule responsabilité est de prendre la prédiction calculée localement et
  les lectures actuelles des capteurs, de les combiner avec la question de
  l'agriculteur, et d'appeler l'IA cloud pour générer une réponse naturelle et
  contextuelle dans la langue choisie (français, arabe ou darija marocaine).

  Flux de données :
    Capteurs → ML Raspberry Pi → (sensor_data + ml_prediction + message)
      → API LLM → réponse en langage naturel (fr / ar / da)
"""

import json
import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

# Chargement des variables d'environnement depuis le fichier .env situé à la
# racine du projet.  On construit le chemin explicitement avec __file__ pour
# que load_dotenv() trouve le bon fichier quelle que soit la façon dont le
# serveur est lancé (ex. `uvicorn backend.app:app` depuis la racine).
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Noms d'affichage des langues utilisés dans le prompt système pour indiquer
# à l'IA dans quelle langue répondre.
_LANG_LABELS = {
    "fr": "français",
    "ar": "arabe classique (العربية الفصحى)",
    "da": "darija marocaine (الدارجة المغربية)",
}


def _get_client() -> OpenAI:
    """
    Crée et retourne un client OpenAI.
    La clé API est vérifiée à l'exécution (pas à l'import) pour éviter
    de bloquer le démarrage du serveur si la clé n'est pas encore configurée.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY n'est pas définie. "
            "Copiez .env.example vers .env et ajoutez votre clé API OpenAI."
        )
    base_url = os.getenv("OPENAI_BASE_URL")
    return OpenAI(api_key=api_key, base_url=base_url)


def generate_expert_response(
    message: str,
    language: str,
    sensor_data: Optional[dict] = None,
    ml_prediction: Optional[str] = None,
) -> str:
    """
    Génère une réponse agricole courte et experte via le LLM cloud.

    Paramètres
    ----------
    message : str
        La question de l'agriculteur (texte ou transcription vocale).
    language : str
        Code de langue cible : "fr" (français), "ar" (arabe), ou "da" (darija).
    sensor_data : dict, optionnel
        Lectures actuelles des capteurs produites par la Raspberry Pi, ex. :
        {"pH": 6.5, "humidity": 42, "temperature": 28,
         "rainfall": 12, "salinity": 0.8}
    ml_prediction : str, optionnel
        Recommandation de culture déjà calculée localement sur la Raspberry Pi
        par le modèle Scikit-Learn (ex. "Olivier" ou "Blé dur").

    Retourne
    --------
    str
        Une réponse concise et experte dans la langue demandée.
    """
    # Récupération du libellé de langue pour le prompt
    lang_label = _LANG_LABELS.get(language, _LANG_LABELS["fr"])

    # Construction du contexte capteurs pour le prompt
    # json.dumps sérialise proprement le dict et évite toute injection de prompt
    if sensor_data:
        # Validation : on ne conserve que les champs numériques attendus
        allowed_keys = {"pH", "ph", "humidity", "temperature", "rainfall", "salinity", "soil_moisture"}
        safe_data = {
            k: v for k, v in sensor_data.items()
            if k in allowed_keys and isinstance(v, (int, float))
        }
        sensor_context = (
            "Voici les données actuelles du sol lues par les capteurs : "
            f"{json.dumps(safe_data, ensure_ascii=False)}. "
        )
    else:
        sensor_context = "Aucune donnée capteur disponible pour le moment. "

    # Construction du contexte prédiction ML pour le prompt
    if ml_prediction:
        ml_context = (
            "La prédiction locale de culture calculée directement sur la Raspberry Pi "
            f"par notre modèle d'Intelligence Artificielle est : {ml_prediction}. "
        )
    else:
        ml_context = ""

    # Prompt système dynamique qui positionne l'IA comme assistant agricole marocain
    system_prompt = (
        "Tu es AgriBot, un expert agricole marocain embarqué sur un robot "
        "Adeept Pi Car équipé d'une Raspberry Pi. "
        + sensor_context
        + ml_context
        + "Réponds à la question de l'agriculteur de manière très courte et précise, "
        f"exclusivement en {lang_label}. "
        "N'ajoute aucune explication sur ta nature ou tes capacités."
    )

    # Appel à l'API OpenAI pour générer la réponse
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        max_tokens=200,
        temperature=0.4,
    )

    return response.choices[0].message.content or ""
