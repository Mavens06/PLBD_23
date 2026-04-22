import json
import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from ml_model.feature_mapping import to_runtime_features

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

_LANG_LABELS = {
    'fr': 'français',
    'ar': 'arabe classique (العربية الفصحى)',
    'da': 'darija marocaine (الدارجة المغربية)',
}
MAX_CHAT_RESPONSE_TOKENS = 200


def _get_client() -> OpenAI:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY n'est pas définie")
    return OpenAI(api_key=api_key, base_url=os.getenv('OPENAI_BASE_URL'))


def generate_expert_response(
    message: str,
    language: str,
    sensor_data: Optional[dict] = None,
    ml_prediction: Optional[str] = None,
) -> str:
    lang_label = _LANG_LABELS.get(language, _LANG_LABELS['fr'])

    if sensor_data:
        safe_data = to_runtime_features(sensor_data)
        sensor_context = (
            'Données terrain mesurées par la Raspberry Pi : '
            f"{json.dumps(safe_data, ensure_ascii=False)}. "
        )
    else:
        sensor_context = 'Aucune donnée capteur disponible. '

    mission_context = f'Contexte mission robot: {ml_prediction}. ' if ml_prediction else ''

    system_prompt = (
        'Tu es AgriBot, assistant agricole relié à un robot mobile sur Raspberry Pi. '
        + sensor_context
        + mission_context
        + 'Réponds de façon courte, pratique et fiable pour un agriculteur. '
        + f'Réponds uniquement en {lang_label}. '
        + "N'invente pas de capteurs ni de variables hors humidité, pH, conductivité et température."
    )

    client = _get_client()
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': message},
        ],
        max_tokens=MAX_CHAT_RESPONSE_TOKENS,
        temperature=0.3,
    )
    return response.choices[0].message.content or ''
