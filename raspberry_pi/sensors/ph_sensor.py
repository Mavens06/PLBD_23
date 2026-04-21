import random

from .base import SensorBase


class PHSensor(SensorBase):
    def read(self) -> float:
        return round(random.uniform(6.0, 6.8), 2)
