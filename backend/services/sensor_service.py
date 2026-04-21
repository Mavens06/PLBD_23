from backend.models.state import SENSOR_HISTORY


def get_measurements():
    return SENSOR_HISTORY[-1], SENSOR_HISTORY


def latest_sensor_dict():
    latest, _ = get_measurements()
    return {
        'humidity': latest['humidity'],
        'ph': latest['ph'],
        'ec': latest['ec'],
        'temp': latest['temp'],
    }
