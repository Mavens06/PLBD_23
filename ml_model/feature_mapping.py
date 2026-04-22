from __future__ import annotations

from typing import Dict

RUNTIME_FEATURES = ('humidity', 'ph', 'ec', 'temp')
ML_FEATURES = ('temperature', 'humidity', 'ph', 'rainfall', 'salinity')


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def to_ml_features(sensor_data: Dict[str, float] | None = None, rainfall: float = 0.0) -> Dict[str, float]:
    """Convertit les données runtime (ec/temp) vers le schéma ML (salinity/temperature)."""
    sensor_data = sensor_data or {}
    temperature = sensor_data.get('temperature', sensor_data.get('temp', 0.0))
    salinity = sensor_data.get('salinity', sensor_data.get('ec', 0.0))
    return {
        'temperature': _to_float(temperature, 0.0),
        'humidity': _to_float(sensor_data.get('humidity', 0.0), 0.0),
        'ph': _to_float(sensor_data.get('ph', 0.0), 0.0),
        'rainfall': _to_float(sensor_data.get('rainfall', rainfall), rainfall),
        'salinity': _to_float(salinity, 0.0),
    }


def to_runtime_features(sensor_data: Dict[str, float] | None = None) -> Dict[str, float]:
    """Convertit vers le schéma runtime frontend/backend (ec/temp)."""
    sensor_data = sensor_data or {}
    return {
        'humidity': _to_float(sensor_data.get('humidity', 0.0), 0.0),
        'ph': _to_float(sensor_data.get('ph', 0.0), 0.0),
        'ec': _to_float(sensor_data.get('ec', sensor_data.get('salinity', 0.0)), 0.0),
        'temp': _to_float(sensor_data.get('temp', sensor_data.get('temperature', 0.0)), 0.0),
    }
