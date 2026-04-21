from ml_model.rules.engine import recommend_actions, recommend_crops


def predict(sensor_data: dict):
    return {
        'top_crops': recommend_crops(sensor_data, top_n=5),
        'actions': recommend_actions(sensor_data),
        'alerts': [
            'Humidité faible' if sensor_data.get('humidity', 0) < 40 else None,
            'Conductivité élevée' if sensor_data.get('ec', 0) > 2.5 else None,
            'pH hors plage' if not 5.8 <= sensor_data.get('ph', 6.5) <= 7.8 else None,
        ],
    }
