from datetime import datetime, timezone
from statistics import median
from time import sleep

from .ec_sensor import ECSensor
from .moisture_sensor import MoistureSensor
from .ph_sensor import PHSensor
from .temperature_sensor import TemperatureSensor


class AcquisitionManager:
    MIN_STABILIZATION_SECONDS = 3
    MAX_STABILIZATION_SECONDS = 5
    MIN_READ_COUNT = 10

    def __init__(self, stabilization_seconds: int = 3, read_count: int = 10):
        self.stabilization_seconds = max(
            self.MIN_STABILIZATION_SECONDS,
            min(self.MAX_STABILIZATION_SECONDS, stabilization_seconds),
        )
        self.read_count = max(self.MIN_READ_COUNT, read_count)
        self._sensors = {
            'humidity': MoistureSensor(),
            'ph': PHSensor(),
            'ec': ECSensor(),
            'temp': TemperatureSensor(),
        }

    def _dispersion(self, values: list[float]) -> float:
        med = median(values)
        abs_dev = [abs(v - med) for v in values]
        return round(float(median(abs_dev)), 3)

    def acquire(self, point: str) -> dict:
        sleep(self.stabilization_seconds)
        raw = {key: [sensor.read() for _ in range(self.read_count)] for key, sensor in self._sensors.items()}
        result = {
            key: {
                'value': round(float(median(values)), 3),
                'dispersion': self._dispersion(values),
            }
            for key, values in raw.items()
        }
        result['timestamp'] = datetime.now(timezone.utc).isoformat()
        result['point'] = point
        return result
