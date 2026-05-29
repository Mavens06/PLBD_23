"""
state.py — État applicatif minimal en mémoire pour le backend Agribotics.

Sert à exposer aux frontends "real_backend" :
  • L'état de la mission (point actif, progression).
  • L'historique des mesures du capteur 4-en-1 RS485 par zone.

Ce singleton est volontairement simple : pas de persistance côté API.
La persistance réelle reste sur la Raspberry Pi (SQLite local), conformément
à l'architecture du projet. Redémarrer le backend remet cet état à zéro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


ZONES = ("A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3")


@dataclass
class RobotState:
    status: str = "idle"               # idle | moving | measuring | done
    active_point: str = "HOME"
    progress_pct: float = 0.0


@dataclass
class Measurement:
    point: str
    humidity: float
    ph: float
    temp: float
    ec: float                          # EC en mS/cm (salinité / conductivité électrique)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    quality: str = "good"

    def as_dict(self) -> dict:
        return {
            "point": self.point,
            "humidity": self.humidity,
            "ph": self.ph,
            "temp": self.temp,
            "ec": self.ec,
            "salinity": self.ec,   # alias frontend
            "timestamp": self.timestamp,
            "quality": self.quality,
        }


@dataclass
class AppState:
    robot: RobotState = field(default_factory=RobotState)
    measurements_by_zone: Dict[str, Measurement] = field(default_factory=dict)
    history: List[Measurement] = field(default_factory=list)

    @property
    def measured_points(self) -> int:
        return len(self.measurements_by_zone)

    @property
    def total_points(self) -> int:
        return len(ZONES)

    def record_measurement(self, m: Measurement) -> None:
        if m.point not in ZONES:
            raise ValueError(f"Point inconnu : {m.point}. Attendu : {ZONES}.")
        self.measurements_by_zone[m.point] = m
        self.history.append(m)
        self.robot.active_point = m.point
        self.robot.progress_pct = round(100 * self.measured_points / self.total_points, 1)
        if self.measured_points >= self.total_points:
            self.robot.status = "done"

    def latest(self) -> Optional[Measurement]:
        return self.history[-1] if self.history else None

    def reset(self) -> None:
        self.robot = RobotState()
        self.measurements_by_zone.clear()
        self.history.clear()


# Singleton partagé par toutes les routes.
APP_STATE = AppState()
