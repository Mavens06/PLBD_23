"""
Couche robot/sonde d'Agribotics — factory selon APP_MODE.

  build_robot()  → AdeeptRobotController (hardware) | MockRobotController (mock)
  build_probe()  → AdeeptProbeController si un servo sonde est configuré,
                   sinon SimulatedProbeController (descente simulée).

Même logique que `sensors/soil_sensor.build_sensor()` : le reste du code
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


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def build_probe(pca=None) -> ProbeController:
    """
    Renvoie la sonde, par ordre de priorité (hardware uniquement) :
      1. `PROBE_NEMA_GPIO=1` → sonde NEMA pilotée DIRECTEMENT par les GPIO de la
         Pi (PiGpioNemaProbeController : STEP/DIR temporisé, sans ESP32).
      2. `PROBE_SERIAL_PORT` défini → sonde NEMA pilotée par un ESP32 en USB
         série (Esp32ProbeController : protocole DOWN/UP + accusé OK).
      3. `PROBE_SERVO_CHANNEL` défini → BRAS du PiCar-Pro (servo : épaule
         canal 2, haut 90° / bas 150°, autres servos en posture home).
      4. sinon → descente simulée.
    `pca` permet de réutiliser le PCA9685 déjà ouvert par le robot (cas servo).
    """
    # 1. Sonde NEMA pilotée directement par les GPIO de la Pi (STEP/DIR).
    if _is_hardware() and _truthy("PROBE_NEMA_GPIO"):
        try:
            from .nema_probe import PiGpioNemaProbeController
            return PiGpioNemaProbeController.from_env()
        except Exception as err:  # pragma: no cover - dépend du matériel
            print(f"[probe] ⚠ NEMA GPIO indisponible ({err}) — repli ESP32/servo/simulé.", flush=True)

    # 2. Sonde NEMA via ESP32 (USB série) — si configurée.
    serial_port = os.getenv("PROBE_SERIAL_PORT")
    if _is_hardware() and serial_port is not None and serial_port.strip() != "":
        try:
            from .esp32_probe import Esp32ProbeController
            return Esp32ProbeController(
                port=serial_port.strip(),
                baud=int(os.getenv("PROBE_SERIAL_BAUD", "115200")),
                ack_timeout=float(os.getenv("PROBE_SERIAL_TIMEOUT", "15")),
                stabilize_s=float(os.getenv("PROBE_STABILIZE_S", "3.0")),
            )
        except Exception as err:  # pragma: no cover - dépend du matériel
            print(f"[probe] ⚠ ESP32 sonde indisponible ({err}) — repli servo/simulé.", flush=True)

    # 2. Sonde servo du PiCar-Pro.
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
