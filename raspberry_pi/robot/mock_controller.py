"""
mock_controller.py — Implémentations mock du robot et de la sonde.

Sert sur PC de dev (aucun GPIO) et de repli si le matériel n'est pas
disponible. Toutes les actions sont seulement journalisées (+ courte pause)
pour rendre la séquence de mission visible dans la console.
"""

from __future__ import annotations

import math
import time

from .base import ProbeController, RobotController


def _log(msg: str) -> None:
    print(f"  [robot:mock] {msg}", flush=True)


class MockRobotController(RobotController):
    """Robot simulé : journalise les déplacements, suit une position fictive."""

    def __init__(self) -> None:
        self._x = 0.0
        self._y = 0.0

    def forward(self, speed: int = 50, duration: float = 1.0) -> None:
        _log(f"avance (speed={speed}, {duration:.1f}s)")
        time.sleep(min(duration, 0.2))

    def backward(self, speed: int = 50, duration: float = 1.0) -> None:
        _log(f"recule (speed={speed}, {duration:.1f}s)")
        time.sleep(min(duration, 0.2))

    def turn_left(self, speed: int = 40, duration: float = 1.0) -> None:
        _log(f"tourne à gauche (speed={speed}, {duration:.1f}s)")
        time.sleep(min(duration, 0.2))

    def turn_right(self, speed: int = 40, duration: float = 1.0) -> None:
        _log(f"tourne à droite (speed={speed}, {duration:.1f}s)")
        time.sleep(min(duration, 0.2))

    def stop(self) -> None:
        _log("STOP")

    def move_to_point(self, x: float, y: float) -> None:
        dist = math.hypot(x - self._x, y - self._y)
        _log(f"va au point (x={x}, y={y}) — distance {dist:.2f} m")
        self._x, self._y = x, y
        time.sleep(0.2)
        self.stop()


class SimulatedProbeController(ProbeController):
    """Sonde simulée : descente/stabilisation/remontée journalisées."""

    def lower_probe(self) -> None:
        _log("sonde : descente (simulée)")
        time.sleep(0.2)

    def stabilize(self, seconds: float = 3.0) -> None:
        _log(f"sonde : stabilisation {seconds:.1f}s (simulée)")
        time.sleep(min(seconds, 0.3))

    def raise_probe(self) -> None:
        _log("sonde : remontée (simulée)")
        time.sleep(0.2)
