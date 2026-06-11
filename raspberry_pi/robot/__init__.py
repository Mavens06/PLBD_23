"""
Couche robot/sonde d'Agribotics — factory selon APP_MODE.

  build_robot()  → AdeeptRobotController (hardware) | MockRobotController (mock)
  build_probe()  → AdeeptProbeController si un servo sonde est configuré,
                   sinon SimulatedProbeController (descente simulée).

Même logique que `sensors/rs485_4in1.build_sensor()` : le reste du code
(orchestrateur de mission) ne dépend que des interfaces de `base.py`, jamais
d'une implémentation concrète. Passer au matériel ne change que la factory.

Sécurité dev : en mode hardware, si l'initialisation matérielle échoue (lib
ou bus I2C absents), on bascule sur le mock avec un message clair plutôt que
de planter l'orchestrateur.
"""

from __future__ import annotations

import os

from .base import ProbeController, RobotController
from .mock_controller import MockRobotController, SimulatedProbeController


def _is_hardware() -> bool:
    return os.getenv("APP_MODE", "mock").strip().lower() == "hardware"


def build_robot() -> RobotController:
    if _is_hardware():
        try:
            from .adeept_controller import AdeeptRobotController
            return AdeeptRobotController()
        except Exception as err:  # pragma: no cover - dépend du matériel
            print(f"[robot] ⚠ init matériel impossible ({err}) — repli mock.", flush=True)
            return MockRobotController()
    return MockRobotController()


def _parse_arm_home(raw: str) -> list[tuple[int, float]]:
    """Parse PROBE_ARM_HOME ("1:90,3:140,4:80") → [(canal, angle), …]."""
    pose: list[tuple[int, float]] = []
    for part in raw.split(","):
        if ":" not in part:
            continue
        ch, deg = part.split(":", 1)
        try:
            pose.append((int(ch.strip()), float(deg.strip())))
        except ValueError:
            continue
    return pose


def build_probe(pca=None) -> ProbeController:
    """
    Renvoie la sonde. Si `PROBE_SERVO_CHANNEL` est défini ET qu'on est en
    hardware, pilote le BRAS du PiCar-Pro (séquence validée : épaule canal 2,
    haut 90° / bas 150°, autres servos en posture home) ; sinon descente
    simulée. `pca` permet de réutiliser le PCA9685 déjà ouvert par le robot.
    """
    channel = os.getenv("PROBE_SERVO_CHANNEL")
    if _is_hardware() and channel is not None and channel.strip() != "":
        try:
            from .adeept_controller import AdeeptProbeController, _envf, _envi
            return AdeeptProbeController(
                channel=_envi("PROBE_SERVO_CHANNEL", 2),
                up_deg=_envf("PROBE_ANGLE_UP", 90),
                down_deg=_envf("PROBE_ANGLE_DOWN", 150),
                stabilize_s=_envf("PROBE_STABILIZE_S", 3.0),
                pca=pca,
                home_pose=_parse_arm_home(
                    os.getenv("PROBE_ARM_HOME", "1:90,3:140,4:80")),
            )
        except Exception as err:  # pragma: no cover - dépend du matériel
            print(f"[probe] ⚠ servo sonde indisponible ({err}) — descente simulée.", flush=True)
    return SimulatedProbeController()


__all__ = [
    "RobotController", "ProbeController",
    "MockRobotController", "SimulatedProbeController",
    "build_robot", "build_probe",
]
