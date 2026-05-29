"""
chatbot_llm.py — Couche conversationnelle d'AgriBot propulsée par le LLM
**Gemini** de Google, servi via l'API Google AI Studio (Generative Language API).

Note d'architecture :
  La Raspberry Pi effectue tout le traitement métier :
    • Lecture du capteur 4-en-1 RS485 (pH, humidité, température, EC/salinité).
    • Exécution du modèle Scikit-Learn local (best_model.pkl) ou du moteur de
      règles fallback pour produire une recommandation de culture.

  Ce module n'effectue AUCUN apprentissage automatique ni traitement capteur.
  Sa seule responsabilité est de prendre la prédiction calculée localement et
  les lectures actuelles des capteurs, de les combiner avec la question de
  l'agriculteur, et d'appeler le LLM **Gemini** (cloud Google AI Studio) pour
  générer une réponse naturelle et contextuelle dans la langue choisie
  (français, arabe classique ou darija marocaine).

  Flux de données :
    Capteurs → ML Raspberry Pi → (sensor_data + ml_prediction + message)
      → LLM Gemini (Google AI Studio) → réponse en langage naturel (fr / ar / da)

  IMPORTANT : contrairement à l'inférence ML/règles qui reste 100% locale,
  cette couche conversationnelle appelle un service cloud. Une connexion
  internet et une clé API (GEMINI_API_KEY) sont donc requises. Seuls le
  message de l'agriculteur et le contexte agronomique (4 variables capteur,
  culture recommandée) sont transmis — jamais d'identifiant personnel.
"""

import json
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

# Chargement des variables d'environnement depuis le fichier .env à la racine.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Configuration Gemini / Google AI Studio (surchargeable via .env).
# Obtenir une clé gratuite : https://aistudio.google.com/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT", "60"))

# Noms d'affichage des langues utilisés dans le prompt système pour indiquer
# au LLM dans quelle langue répondre.
_LANG_LABELS = {
    "fr": "français",
    "ar": "arabe classique (العربية الفصحى)",
    "da": "darija marocaine (الدارجة المغربية, transcrite en lettres arabes)",
}

# Cultures cibles de la V1 (cohérent avec frontend/data_model.js et
# ml_model/rules/crop_catalog.py). Aucune culture hors-périmètre.
_TARGET_CROPS = (
    "Blé, Tomate, Oignon, Carotte, Pomme de terre, Orge, "
    "Betterave à sucre, Olivier, Vigne, Pastèque"
)

# Champs capteurs autorisés — strictement les 4 variables du capteur 4-en-1 RS485.
# N/P/K sont volontairement exclus : le capteur ne les mesure pas.
_ALLOWED_SENSOR_KEYS = {"pH", "humidity", "temperature", "salinity"}


def _build_sensor_context(sensor_data: Optional[dict]) -> str:
    """Sérialise les lectures capteur en contexte texte pour le prompt."""
    if not sensor_data:
        return "Aucune donnée capteur disponible pour le moment. "
    safe_data = {
        k: v for k, v in sensor_data.items()
        if k in _ALLOWED_SENSOR_KEYS and isinstance(v, (int, float))
    }
    if not safe_data:
        return "Aucune donnée capteur valide disponible. "
    return (
        "Voici les données actuelles du sol lues par le capteur 4-en-1 RS485 : "
        f"{json.dumps(safe_data, ensure_ascii=False)} "
        "(humidité en %, température en °C, salinité/EC en mS/cm). "
    )


def _build_system_prompt(
    language: str,
    sensor_data: Optional[dict],
    ml_prediction: Optional[str],
    selected_zone: Optional[str],
    selected_crop: Optional[str],
    robot_state: Optional[dict],
    correction_context: Optional[str] = None,
) -> str:
    """Compose un prompt système robuste, ancré sur les données réelles."""
    lang_label = _LANG_LABELS.get(language, _LANG_LABELS["fr"])

    sensor_context = _build_sensor_context(sensor_data)

    if ml_prediction:
        ml_context = (
            "La prédiction locale de culture calculée par notre modèle "
            f"d'Intelligence Artificielle est : {ml_prediction}. "
        )
    else:
        ml_context = ""

    # Diagnostic de correction du sol déjà calculé (déterministe). Le LLM doit
    # s'appuyer dessus sans inventer d'autre conseil agronomique.
    correction_block = (correction_context + " ") if correction_context else ""

    zone_context = f"Zone analysée : {selected_zone}. " if selected_zone else ""
    crop_context = f"Culture cible choisie par l'agriculteur : {selected_crop}. " if selected_crop else ""

    if robot_state and isinstance(robot_state, dict):
        active = robot_state.get("activePoint") or robot_state.get("active_point")
        measured = robot_state.get("measuredPoints") or robot_state.get("measured_points")
        total = robot_state.get("totalPoints") or robot_state.get("total_points")
        robot_context = ""
        if active:
            robot_context += f"Le robot est actuellement au point {active}. "
        if measured is not None and total is not None:
            robot_context += f"Progression de la mission : {measured}/{total} points mesurés. "
    else:
        robot_context = ""

    return (
        "Tu es AgriBot, un expert agricole marocain embarqué sur un robot "
        "Adeept Pi Car équipé d'une Raspberry Pi et d'un capteur industriel "
        "4-en-1 RS485 (Modbus RTU) qui mesure UNIQUEMENT quatre variables du sol : "
        "pH, humidité, température, et conductivité électrique (EC, exprimée en mS/cm, "
        "indicateur de salinité). "
        "IMPORTANT : tu ne disposes JAMAIS de mesures d'azote (N), de phosphore (P) "
        "ou de potassium (K). Ne mentionne jamais N/P/K et ne propose pas d'engrais "
        "basés sur ces éléments. "
        f"Les seules cultures cibles à recommander sont : {_TARGET_CROPS}. "
        + sensor_context
        + ml_context
        + zone_context
        + crop_context
        + robot_context
        + correction_block
        + "Réponds à la question de l'agriculteur de manière courte (2 à 4 phrases), "
        "concrète et actionnable, en t'appuyant EXCLUSIVEMENT sur les données et le "
        "diagnostic ci-dessus. N'invente aucune correction ou conseil non listé. "
        "Si une culture mieux adaptée au sol est indiquée, mentionne-la brièvement à la fin. "
        f"Réponds EXCLUSIVEMENT en {lang_label}. "
        "N'ajoute aucune explication sur ta nature, tes capacités ou ton fonctionnement interne."
    )


async def generate_expert_response(
    message: str,
    language: str,
    sensor_data: Optional[dict] = None,
    ml_prediction: Optional[str] = None,
    selected_zone: Optional[str] = None,
    selected_crop: Optional[str] = None,
    robot_state: Optional[dict] = None,
    correction_context: Optional[str] = None,
) -> str:
    """
    Génère une réponse agricole courte et experte via le LLM Gemini (cloud).

    L'appel HTTP est asynchrone (httpx.AsyncClient) pour ne pas bloquer la
    boucle évènementielle FastAPI : plusieurs requêtes peuvent être traitées
    en parallèle sans saturer le serveur.

    Paramètres
    ----------
    message : str
        Question de l'agriculteur (texte ou transcription vocale).
    language : str
        Code de langue cible : "fr" (français), "ar" (arabe), "da" (darija).
    sensor_data : dict, optionnel
        Lectures actuelles du capteur 4-en-1 RS485, ex. :
        {"pH": 6.5, "humidity": 42, "temperature": 28, "salinity": 1.2}
    ml_prediction : str, optionnel
        Recommandation de culture déjà calculée localement
        (ex. "Olivier" ou "Blé dur").
    selected_zone : str, optionnel
        Zone du champ sélectionnée par l'agriculteur (ex. "B2").
    selected_crop : str, optionnel
        Culture cible choisie par l'agriculteur (ex. "Tomate").
    robot_state : dict, optionnel
        État de mission du robot (point actif, progression).

    Retourne
    --------
    str
        Réponse concise et experte dans la langue demandée.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY manquante. Renseignez-la dans le fichier .env "
            "(clé gratuite : https://aistudio.google.com/apikey)."
        )

    system_prompt = _build_system_prompt(
        language=language,
        sensor_data=sensor_data,
        ml_prediction=ml_prediction,
        selected_zone=selected_zone,
        selected_crop=selected_crop,
        robot_state=robot_state,
        correction_context=correction_context,
    )

    # Format de l'API Generative Language : le prompt système passe par
    # `system_instruction`, le message utilisateur par `contents`.
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [
            {"role": "user", "parts": [{"text": message}]},
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 220,
        },
    }

    url = f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent"
    async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
        try:
            response = await client.post(
                url,
                params={"key": GEMINI_API_KEY},
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as err:
            raise RuntimeError(
                f"Échec de l'appel au LLM Gemini ({url}, modèle={GEMINI_MODEL}). "
                "Vérifiez votre connexion internet et la validité de GEMINI_API_KEY."
            ) from err

    data = response.json()
    # Réponse Gemini : candidates[0].content.parts[*].text
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()
