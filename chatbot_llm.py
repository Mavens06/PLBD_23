"""
chatbot_llm.py – AgriBot conversational layer powered by an OpenAI LLM.

Architecture note:
  The Raspberry Pi handles ALL the heavy lifting:
    • Reading physical sensors (pH, humidity, temperature, N/P/K, salinity)
    • Running the local Scikit-Learn model (best_model.pkl) to produce a crop
      recommendation (ml_prediction).

  This module does NOT perform any machine-learning or sensor processing.
  Its sole responsibility is to take the locally computed prediction and the
  current sensor readings, combine them with the farmer's question, and call
  the cloud LLM to generate a natural, context-aware response in the language
  chosen by the user (French, Arabic, or Moroccan Darija).

  Data flow:
    Sensors → Raspberry Pi ML → (sensor_data + ml_prediction + user_query)
      → LLM API → natural-language response (fr / ar / da)
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Language display names used inside the system prompt so the LLM knows which
# language to reply in.
_LANG_LABELS = {
    "fr": "français",
    "ar": "arabe classique (العربية الفصحى)",
    "da": "darija marocaine (الدارجة المغربية)",
}

_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise EnvironmentError(
        "OPENAI_API_KEY is not set. "
        "Copy .env.example to .env and add your OpenAI API key."
    )

# A single shared client instance.
_client = OpenAI(api_key=_api_key)


def generate_expert_response(
    user_query: str,
    lang: str,
    sensor_data: dict,
    ml_prediction: str,
) -> str:
    """
    Generate a short, expert agricultural response via the cloud LLM.

    Parameters
    ----------
    user_query : str
        The farmer's question (text or voice-transcription).
    lang : str
        Target language code: "fr" (French), "ar" (Arabic), or "da" (Darija).
    sensor_data : dict
        Current sensor readings as produced by the Raspberry Pi, e.g.:
        {"pH": 6.5, "humidity": 42, "temperature": 28, "N": 120,
         "P": 55, "K": 200, "salinity": 0.8}
    ml_prediction : str
        The crop recommendation already calculated locally on the Raspberry Pi
        by the Scikit-Learn model (e.g. "Olivier" or "Blé dur").

    Returns
    -------
    str
        A concise, expert answer in the requested language.
    """
    lang_label = _LANG_LABELS.get(lang, _LANG_LABELS["fr"])

    system_prompt = (
        "Tu es AgriBot, un expert agricole marocain embarqué sur un robot "
        "Adeept Pi Car équipé d'une Raspberry Pi. "
        "Voici les données actuelles du sol lues par les capteurs : "
        f"{sensor_data}. "
        "La prédiction locale de culture calculée directement sur la Raspberry Pi "
        f"par notre modèle d'Intelligence Artificielle est : {ml_prediction}. "
        "Réponds à la question de l'agriculteur de manière très courte et précise, "
        f"exclusivement en {lang_label}. "
        "N'ajoute aucune explication sur ta nature ou tes capacités."
    )

    response = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        max_tokens=200,
        temperature=0.4,
    )

    return response.choices[0].message.content or ""
