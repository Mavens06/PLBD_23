"""
adeept_controller.py — Pilotage RÉEL du robot Adeept PiCar-Pro.

Calqué sur le code validé sur le robot de l'équipe :
  • PCA9685 (adafruit_pca9685) à l'adresse 0x5f, 50 Hz.
  • 2 moteurs DC (adafruit_motor.motor.DCMotor) :
        moteur G = canaux PCA (15, 14)
        moteur D = canaux PCA (12, 13)
  • 1 servo de DIRECTION (adafruit_motor.servo.Servo) sur le canal 0 :
        centre = 70°, gauche = 35°, droite = 125°.

Architecture « voiture » (2 moteurs de propulsion + 1 servo de braquage),
PAS du différentiel : on tourne en braquant le servo de direction puis en
avançant brièvement.

Limite assumée (pas d'odométrie/encodeurs sur ce robot) : `move_to_point`
fait du *dead-reckoning temporisé* — il avance une durée proportionnelle à la
distance entre points (vitesse calibrée par `ROBOT_SPEED_MPS`). C'est l'approche
des trajectoires temporisées déjà utilisée sur le robot. Pour une précision
supérieure plus tard : suiveur de ligne ou encodeurs, sans changer cette interface.

Toutes les valeurs sont surchargeables par variables d'environnement (cf. .env.example).
Les imports matériels (busio, adafruit_*) sont PARESSEUX (dans __init__) pour que
ce module reste importable sur un PC de dev sans GPIO.
"""

from __future__ import annotations

import math
import os
import time

from .base import ProbeController, RobotController


def _log(msg: str) -> None:
    print(f"  [robot:adeept] {msg}", flush=True)


def _envf(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


def _envi(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


class AdeeptRobotController(RobotController):
    """Pilote réel des moteurs + servo de direction du PiCar-Pro."""

    def __init__(self) -> None:
        # Imports matériels paresseux : ne s'exécutent que sur la Pi.
        import board
        import busio
        from adafruit_pca9685 import PCA9685
        from adafruit_motor import motor as _motor

        self._motor_lib = _motor

        # --- Configuration (défauts = valeurs validées sur le robot) --------
        self._addr = int(os.getenv("PCA9685_ADDRESS", "0x5f"), 0)
        self._freq = _envi("PCA9685_FREQUENCY", 50)
        m1a, m1b = _envi("MOTOR_LEFT_IN1", 15), _envi("MOTOR_LEFT_IN2", 14)
        m2a, m2b = _envi("MOTOR_RIGHT_IN1", 12), _envi("MOTOR_RIGHT_IN2", 13)
        self._steer_ch = _envi("STEER_SERVO_CHANNEL", 0)
        self._steer_center = _envf("STEER_CENTER_DEG", 70)
        self._steer_left = _envf("STEER_LEFT_DEG", 35)
        self._steer_right = _envf("STEER_RIGHT_DEG", 125)
        # Throttle [0..1] correspondant à speed=100. Les essais robot tournent
        # autour de 0.07–0.09, on plafonne donc volontairement bas.
        self._throttle_scale = _envf("DRIVE_THROTTLE_SCALE", 0.12)
        self._speed_mps = _envf("ROBOT_SPEED_MPS", 0.30)

        # --- Initialisation matérielle --------------------------------------
        i2c = busio.I2C(board.SCL, board.SDA)
        self._pca = PCA9685(i2c, address=self._addr)
        self._pca.frequency = self._freq
        self._left = _motor.DCMotor(self._pca.channels[m1a], self._pca.channels[m1b])
        self._right = _motor.DCMotor(self._pca.channels[m2a], self._pca.channels[m2b])

        self._x = 0.0
        self._y = 0.0
        self._set_angle(self._steer_ch, self._steer_center)
        _log(f"prêt (PCA 0x{self._addr:02x} @ {self._freq}Hz, scale={self._throttle_scale})")

    # -- Bas niveau ----------------------------------------------------------
    def _set_angle(self, channel: int, angle: float) -> None:
        """Positionne un servo (mirroir exact du set_angle validé)."""
        from adafruit_motor import servo
        s = servo.Servo(self._pca.channels[channel], min_pulse=500, max_pulse=2400,
                        actuation_range=180)
        s.angle = max(0.0, min(180.0, float(angle)))

    def _throttle(self, value: float) -> None:
        value = max(-1.0, min(1.0, value))
        self._left.throttle = value
        self._right.throttle = value

    def _speed_to_throttle(self, speed: int) -> float:
        return (max(0, min(100, speed)) / 100.0) * self._throttle_scale

    # -- Interface RobotController ------------------------------------------
    def forward(self, speed: int = 50, duration: float = 1.0) -> None:
        _log(f"avance (speed={speed}, {duration:.1f}s)")
        self._throttle(self._speed_to_throttle(speed))
        time.sleep(max(0.0, duration))
        self._throttle(0.0)

    def backward(self, speed: int = 50, duration: float = 1.0) -> None:
        _log(f"recule (speed={speed}, {duration:.1f}s)")
        self._throttle(-self._speed_to_throttle(speed))
        time.sleep(max(0.0, duration))
        self._throttle(0.0)

    def turn_left(self, speed: int = 40, duration: float = 1.0) -> None:
        _log(f"tourne à gauche (speed={speed}, {duration:.1f}s)")
        self._set_angle(self._steer_ch, self._steer_left)
        self._throttle(self._speed_to_throttle(speed))
        time.sleep(max(0.0, duration))
        self._throttle(0.0)
        self._set_angle(self._steer_ch, self._steer_center)

    def turn_right(self, speed: int = 40, duration: float = 1.0) -> None:
        _log(f"tourne à droite (speed={speed}, {duration:.1f}s)")
        self._set_angle(self._steer_ch, self._steer_right)
        self._throttle(self._speed_to_throttle(speed))
        time.sleep(max(0.0, duration))
        self._throttle(0.0)
        self._set_angle(self._steer_ch, self._steer_center)

    def stop(self) -> None:
        # Arrêt d'urgence : doit rester fiable même si un servo échoue.
        try:
            self._throttle(0.0)
        finally:
            try:
                self._set_angle(self._steer_ch, self._steer_center)
            except Exception:
                pass
        _log("STOP")

    def move_to_point(self, x: float, y: float) -> None:
        dist = math.hypot(x - self._x, y - self._y)
        duration = dist / self._speed_mps if self._speed_mps > 0 else 0.0
        _log(f"va au point (x={x}, y={y}) — {dist:.2f} m ≈ {duration:.1f}s "
             f"(dead-reckoning, {self._speed_mps} m/s)")
        if duration > 0:
            self.forward(speed=70, duration=duration)
        self._x, self._y = x, y
        self.stop()

    def close(self) -> None:
        try:
            self.stop()
        finally:
            try:
                self._pca.deinit()
            except Exception:
                pass


class AdeeptProbeController(ProbeController):
    """
    Sonde sur servo (optionnelle — non montée pour l'instant).

    Activée seulement si `PROBE_SERVO_CHANNEL` est défini. Tant que le servo
    n'est pas monté, on utilise `SimulatedProbeController` (cf. __init__.py).
    Réutilise le même PCA9685 que le robot si fourni, sinon en ouvre un.
    """

    def __init__(self, channel: int, up_deg: float, down_deg: float,
                 stabilize_s: float, pca=None) -> None:
        self._channel = channel
        self._up = up_deg
        self._down = down_deg
        self._stab = stabilize_s
        if pca is None:
            import board
            import busio
            from adafruit_pca9685 import PCA9685
            i2c = busio.I2C(board.SCL, board.SDA)
            pca = PCA9685(i2c, address=int(os.getenv("PCA9685_ADDRESS", "0x5f"), 0))
            pca.frequency = _envi("PCA9685_FREQUENCY", 50)
        self._pca = pca
        self._set_angle(self._up)

    def _set_angle(self, angle: float) -> None:
        from adafruit_motor import servo
        s = servo.Servo(self._pca.channels[self._channel], min_pulse=500,
                        max_pulse=2400, actuation_range=180)
        s.angle = max(0.0, min(180.0, float(angle)))

    def lower_probe(self) -> None:
        _log(f"sonde : descente (servo {self._channel} → {self._down}°)")
        self._set_angle(self._down)
        time.sleep(0.5)

    def stabilize(self, seconds: float = None) -> None:  # type: ignore[assignment]
        s = self._stab if seconds is None else seconds
        _log(f"sonde : stabilisation {s:.1f}s")
        time.sleep(max(0.0, s))

    def raise_probe(self) -> None:
        _log(f"sonde : remontée (servo {self._channel} → {self._up}°)")
        self._set_angle(self._up)
        time.sleep(0.5)
