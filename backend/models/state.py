from datetime import datetime, timedelta


def _ts(minutes_ago: int) -> datetime:
    return datetime.utcnow() - timedelta(minutes=minutes_ago)


SENSOR_HISTORY = [
    {'humidity': 46.0, 'ph': 6.5, 'ec': 1.3, 'temp': 21.2, 'timestamp': _ts(40), 'quality': 'good'},
    {'humidity': 44.0, 'ph': 6.4, 'ec': 1.5, 'temp': 21.8, 'timestamp': _ts(30), 'quality': 'good'},
    {'humidity': 42.0, 'ph': 6.3, 'ec': 1.8, 'temp': 22.4, 'timestamp': _ts(20), 'quality': 'warning'},
    {'humidity': 41.0, 'ph': 6.2, 'ec': 2.0, 'temp': 22.9, 'timestamp': _ts(10), 'quality': 'warning'},
]

ROBOT_STATE = {
    'status': 'Actif',
    'mission': 'Cartographie parcelle nord',
    'active_point': 'B3',
    'progress_pct': 58,
    'total_points': 24,
    'measured_points': 14,
}

WEATHER = {
    'temperature_c': 24.0,
    'humidity_pct': 35.0,
    'wind_kmh': 16.0,
    'rain_mm_next_24h': 0.0,
}
