from .crop_catalog import CROP_CATALOG

MAX_RECOMMENDED_CROPS = 10


def _range_score(value: float, lo: float, hi: float) -> float:
    if lo <= value <= hi:
        return 1.0
    if value < lo:
        return max(0.0, 1 - (lo - value) / max(1, lo))
    return max(0.0, 1 - (value - hi) / max(1, hi))


def _ec_score(ec: float, ec_max: float) -> float:
    return 1.0 if ec <= ec_max else max(0.0, 1 - (ec - ec_max) / ec_max)


def recommend_crops(sensor_data: dict, top_n: int = 5):
    humidity = float(sensor_data.get('humidity', 0))
    ph = float(sensor_data.get('ph', 0))
    ec = float(sensor_data.get('ec', 0))
    temp = float(sensor_data.get('temp', 0))

    scored = []
    for crop in CROP_CATALOG:
        score = 0.0
        score += 0.35 * _range_score(humidity, *crop['humidity'])
        score += 0.25 * _range_score(ph, *crop['ph'])
        score += 0.2 * _range_score(temp, *crop['temp'])
        score += 0.2 * _ec_score(ec, crop['ec_max'])
        scored.append({'name': crop['name'], 'category': crop['category'], 'score': round(score * 100, 1)})

    return sorted(scored, key=lambda x: x['score'], reverse=True)[:max(1, min(top_n, MAX_RECOMMENDED_CROPS))]


def recommend_actions(sensor_data: dict):
    actions = []
    if sensor_data.get('humidity', 0) < 45:
        actions.append('Augmenter l\'irrigation localisée sur les zones les plus sèches.')
    if sensor_data.get('ec', 0) > 1.8:
        actions.append('Prévoir un lessivage court pour limiter l\'accumulation de sels.')
    if sensor_data.get('ph', 0) < 6.0:
        actions.append('Programmer un amendement calcique progressif.')
    if sensor_data.get('temp', 0) > 30:
        actions.append('Réduire les opérations en milieu de journée et privilégier matin/soir.')
    if not actions:
        actions.append('Maintenir la stratégie actuelle et poursuivre le suivi des 4 capteurs.')
    return actions[:3]
