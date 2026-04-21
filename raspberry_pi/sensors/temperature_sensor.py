import random

from .base import SensorBase


class TemperatureSensor(SensorBase):
    def read(self) -> float:
        return round(random.uniform(18.0, 28.0), 1)
