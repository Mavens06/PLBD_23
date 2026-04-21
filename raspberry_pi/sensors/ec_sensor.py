import random

from .base import SensorBase


class ECSensor(SensorBase):
    def read(self) -> float:
        return round(random.uniform(0.9, 2.4), 2)
