import random

from .base import SensorBase


class MoistureSensor(SensorBase):
    def read(self) -> float:
        return round(random.uniform(38.0, 55.0), 1)
