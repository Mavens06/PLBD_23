from backend.models.state import SENSOR_HISTORY, WEATHER
from ml_model.feature_mapping import to_runtime_features
from ml_model.inference.predict import predict
from ml_model.rules.crop_catalog import CROP_CATALOG

DEFAULT_CROPS = [crop['name'] for crop in CROP_CATALOG]
MAX_ACTION_TITLE_LENGTH = 90


def _priority_from_text(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ('urgent', 'immédiat', 'salinit', 'lessivage', 'irrigation')):
        return 'high'
    if any(token in lower for token in ('ph', 'amendement', 'température')):
        return 'medium'
    return 'low'


def _to_action_item(action) -> dict:
    if isinstance(action, dict):
        return {
            'title': action.get('title', 'Action recommandée'),
            'detail': action.get('detail', ''),
            'priority': action.get('priority', 'medium'),
        }
    detail = str(action).strip()
    return {
        'title': detail.split('.')[0][:MAX_ACTION_TITLE_LENGTH] or 'Action recommandée',
        'detail': detail or 'Maintenir le suivi des capteurs.',
        'priority': _priority_from_text(detail),
    }


def get_recommendations():
    latest_runtime = to_runtime_features(SENSOR_HISTORY[-1])
    latest_for_inference = {
        **latest_runtime,
        'rainfall': WEATHER.get('rain_mm_next_24h', 0.0),
    }

    result = predict(latest_for_inference)
    actions = [_to_action_item(action) for action in result.get('actions', [])][:3]
    if not actions:
        actions = [{
            'title': 'Maintenir la cadence de mesure',
            'detail': 'Conserver un cycle de mesures stable pour fiabiliser la carte.',
            'priority': 'low',
        }]

    crops = []
    for item in result.get('top_crops', []):
        if isinstance(item, dict):
            name = item.get('name')
        else:
            name = str(item)
        if name:
            crops.append(name)

    return {'actions': actions, 'crops': crops[:5] or DEFAULT_CROPS[:5]}
