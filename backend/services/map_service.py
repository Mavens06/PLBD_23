from backend.models.state import SENSOR_HISTORY


GRID_POINTS = [
    {'zone': 'A1', 'x': 1, 'y': 1}, {'zone': 'A2', 'x': 2, 'y': 1}, {'zone': 'A3', 'x': 3, 'y': 1},
    {'zone': 'B1', 'x': 1, 'y': 2}, {'zone': 'B2', 'x': 2, 'y': 2}, {'zone': 'B3', 'x': 3, 'y': 2},
    {'zone': 'C1', 'x': 1, 'y': 3}, {'zone': 'C2', 'x': 2, 'y': 3}, {'zone': 'C3', 'x': 3, 'y': 3},
]


def get_map_points(variable: str):
    base = SENSOR_HISTORY[-1]
    values = {
        'humidity': [base['humidity'] - 8, base['humidity'] - 2, base['humidity'] + 1, base['humidity'] - 5, base['humidity'], base['humidity'] + 2, base['humidity'] - 6, base['humidity'] - 1, base['humidity'] + 3],
        'ph': [base['ph'] - 0.4, base['ph'] - 0.2, base['ph'], base['ph'] - 0.3, base['ph'], base['ph'] + 0.1, base['ph'] - 0.2, base['ph'] + 0.1, base['ph'] + 0.2],
        'ec': [base['ec'] + 0.4, base['ec'] + 0.2, base['ec'] - 0.1, base['ec'] + 0.5, base['ec'], base['ec'] - 0.1, base['ec'] + 0.3, base['ec'] + 0.1, base['ec'] - 0.2],
        'temp': [base['temp'] - 1.8, base['temp'] - 1.0, base['temp'] - 0.4, base['temp'] - 1.2, base['temp'], base['temp'] + 0.3, base['temp'] - 0.8, base['temp'] + 0.1, base['temp'] + 0.4],
    }
    pts = []
    for i, point in enumerate(GRID_POINTS):
        pts.append({**point, 'value': round(values[variable][i], 2)})
    return pts
