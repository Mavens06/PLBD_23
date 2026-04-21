from backend.models.state import SENSOR_HISTORY

CROPS = [
    'Blé', 'Orge', 'Maïs', 'Tomate', 'Pomme de terre',
    'Oignon', 'Olivier', 'Agrumes', 'Luzerne', 'Pois chiche',
]


def get_recommendations():
    latest = SENSOR_HISTORY[-1]
    actions = []
    if latest['humidity'] < 45:
        actions.append({'title': 'Irrigation légère', 'detail': 'Appliquer 12–18 mm en priorité sur A1/B1.', 'priority': 'high'})
    if latest['ec'] >= 1.8:
        actions.append({'title': 'Réduire la salinité', 'detail': 'Prévoir un lessivage contrôlé sur zones critiques.', 'priority': 'high'})
    if latest['ph'] < 6.0:
        actions.append({'title': 'Corriger le pH', 'detail': 'Amendement calcique progressif sur la prochaine tournée.', 'priority': 'medium'})
    if len(actions) < 3:
        actions.append({'title': 'Maintenir la cadence de mesure', 'detail': 'Conserver un cycle de 24 points pour stabiliser la carte.', 'priority': 'low'})
    return {'actions': actions[:3], 'crops': CROPS[:5]}
