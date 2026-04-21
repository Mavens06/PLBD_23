from backend.chatbot_llm import generate_expert_response
from .sensor_service import latest_sensor_dict


FALLBACK_MESSAGES = {
    'fr': "Je recommande d'arroser les zones les plus sèches, surveiller la conductivité, et terminer le point actif avant de changer de secteur.",
    'ar': 'أنصح بري المناطق الأكثر جفافًا، ومراقبة التوصيلية، وإنهاء النقطة النشطة قبل الانتقال.',
    'da': 'نسقيُو الزون الناشفة لول، نراقبو الكوندوكتيڤيتي، ونكملو النقطة النشطة قبل ما نبدلو القطاع.',
}


def build_chat_response(
    message: str,
    language: str,
    sensor_data: dict | None = None,
    robot_state: str | None = None,
):
    context_data = sensor_data or latest_sensor_dict()
    try:
        return generate_expert_response(
            message=message,
            language=language,
            sensor_data=context_data,
            ml_prediction=robot_state,
        )
    except Exception:
        return FALLBACK_MESSAGES.get(language, FALLBACK_MESSAGES['fr'])
