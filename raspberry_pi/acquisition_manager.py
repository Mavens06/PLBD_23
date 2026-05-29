"""
acquisition_manager.py — Protocole d'acquisition d'une mesure de point.

Pour chaque point de la grille :
  1) optionnel : stabilisation 4 s (en hardware uniquement) — laisse le
     capteur s'équilibrer dans la nouvelle terre.
  2) 10 lectures successives à intervalle régulier.
  3) calcul des statistiques (moyenne, médiane, écart-type de la population)
     pour chaque variable.
  4) renvoie un MeasurementRecord prêt à être loggé / envoyé à l'API.

Le résultat est un MeasurementRecord cohérent avec le schéma backend
(POST /api/measurements).
"""

from __future__ import annotations

import os
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from .sensors.rs485_4in1 import Sensor, SensorReading


# ---------------------------------------------------------------------------
# Schéma de sortie
# ---------------------------------------------------------------------------

@dataclass
class StatTriplet:
    mean: float
    median: float
    pstdev: float

    def as_dict(self) -> dict:
        return {"mean": round(self.mean, 3),
                "median": round(self.median, 3),
                "pstdev": round(self.pstdev, 3)}


@dataclass
class MeasurementRecord:
    point: str
    humidity: float
    ph: float
    temp: float
    ec: float
    stats: dict = field(default_factory=dict)
    quality: str = "good"
    samples: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict:
        return {
            "point": self.point,
            "humidity": self.humidity,
            "ph": self.ph,
            "temp": self.temp,
            "ec": self.ec,
            "stats": self.stats,
            "quality": self.quality,
            "samples": self.samples,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Gestionnaire d'acquisition
# ---------------------------------------------------------------------------

class AcquisitionManager:
    """Coordonne la lecture stabilisée d'un point de mesure."""

    DEFAULT_SAMPLES = 10
    DEFAULT_INTERVAL_S = 0.5
    DEFAULT_STABILIZATION_S = 4.0   # appliquée uniquement en mode hardware

    def __init__(
        self,
        sensor: Sensor,
        samples: int = DEFAULT_SAMPLES,
        interval_s: float = DEFAULT_INTERVAL_S,
        stabilization_s: float | None = None,
    ) -> None:
        self._sensor = sensor
        self._samples = max(1, samples)
        self._interval_s = max(0.0, interval_s)
        if stabilization_s is None:
            stabilization_s = (
                self.DEFAULT_STABILIZATION_S
                if os.getenv("APP_MODE", "mock").lower() == "hardware"
                else 0.0
            )
        self._stabilization_s = stabilization_s

    @staticmethod
    def _stats(values: List[float]) -> StatTriplet:
        n = len(values)
        return StatTriplet(
            mean=statistics.fmean(values),
            median=statistics.median(values),
            pstdev=statistics.pstdev(values) if n > 1 else 0.0,
        )

    @staticmethod
    def _quality(pstdev_ph: float, pstdev_ec: float) -> str:
        """Qualité grossière à partir de l'écart-type pH et EC."""
        if pstdev_ph > 0.3 or pstdev_ec > 0.4:
            return "noisy"
        if pstdev_ph > 0.15 or pstdev_ec > 0.2:
            return "fair"
        return "good"

    def collect(self, point: str, x: float | None = None, y: float | None = None) -> MeasurementRecord:
        """
        Exécute le protocole complet sur un point donné.

        `point` (label) et, si fournies, les coordonnées (x, y) sont passés au
        sensor mock pour qu'il prenne le bon profil de zone / champ de sol
        (no-op en hardware).
        """
        # Positionnement du mock (label + coordonnées éventuelles ; no-op hardware)
        if hasattr(self._sensor, "set_location"):
            self._sensor.set_location(point, x, y)
        elif hasattr(self._sensor, "set_profile"):
            self._sensor.set_profile(point)
        # Stabilisation (mock = 0 s, hardware = 4 s)
        if self._stabilization_s > 0:
            time.sleep(self._stabilization_s)

        readings: List[SensorReading] = []
        for i in range(self._samples):
            readings.append(self._sensor.read())
            if i < self._samples - 1 and self._interval_s > 0:
                time.sleep(self._interval_s)

        humidities = [r.humidity for r in readings]
        phs        = [r.ph        for r in readings]
        temps      = [r.temperature for r in readings]
        ecs        = [r.ec        for r in readings]

        s_h = self._stats(humidities)
        s_p = self._stats(phs)
        s_t = self._stats(temps)
        s_e = self._stats(ecs)

        return MeasurementRecord(
            point=point,
            humidity=round(s_h.median, 2),
            ph=round(s_p.median, 2),
            temp=round(s_t.median, 2),
            ec=round(s_e.median, 3),
            stats={
                "humidity": s_h.as_dict(),
                "ph": s_p.as_dict(),
                "temperature": s_t.as_dict(),
                "ec": s_e.as_dict(),
            },
            quality=self._quality(s_p.pstdev, s_e.pstdev),
            samples=self._samples,
        )
