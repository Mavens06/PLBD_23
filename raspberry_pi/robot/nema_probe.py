"""
nema_probe.py - Probe controller for a NEMA17 + A4988 driven by Raspberry Pi GPIO.

This adapts the standalone /home/pi/code.py motor test into the mission flow:
run_mission() calls lower_probe(), stabilize(), then raise_probe().
"""

from __future__ import annotations

import os
import threading
import time

from .base import ProbeController


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _direction_level(value: str, default_high: bool) -> bool:
    raw = (value or "").strip().upper()
    if raw in ("H", "HIGH", "1", "UP"):
        return True
    if raw in ("L", "LOW", "0", "B", "DOWN"):
        return False
    return default_high


class PiGpioNemaProbeController(ProbeController):
    """Controls probe up/down motion with STEP/DIR GPIO pins."""

    def __init__(
        self,
        step_pin: int = 26,
        dir_pin: int = 27,
        steps_per_rev: int = 200,
        rpm: int = 150,
        down_s: float = 9.0,
        up_s: float | None = None,
        down_high: bool = False,
        up_high: bool = True,
        stabilize_s: float = 3.0,
        start_rpm: int = 50,
        accel_s: float = 1.2,
        gpio=None,
    ) -> None:
        if gpio is None:
            import RPi.GPIO as GPIO  # pragma: no cover - only available on the Pi
            gpio = GPIO

        self._gpio = gpio
        self._step_pin = step_pin
        self._dir_pin = dir_pin
        self._steps_per_rev = max(1, steps_per_rev)
        self._rpm = max(1, rpm)
        self._down_s = max(0.0, down_s)
        self._up_s = max(0.0, up_s if up_s is not None else down_s)
        self._down_high = down_high
        self._up_high = up_high
        self._stabilize_s = max(0.0, stabilize_s)
        self._start_rpm = max(1, min(start_rpm, self._rpm))
        self._accel_s = max(0.0, accel_s)
        self._lock = threading.Lock()
        self._closed = False

        gpio.setwarnings(False)
        gpio.setmode(gpio.BCM)
        gpio.setup(self._step_pin, gpio.OUT)
        gpio.setup(self._dir_pin, gpio.OUT)
        gpio.output(self._step_pin, gpio.LOW)
        gpio.output(self._dir_pin, gpio.HIGH if self._down_high else gpio.LOW)
        print(
            f"[probe:nema] GPIO STEP={self._step_pin} DIR={self._dir_pin} "
            f"rpm={self._start_rpm}→{self._rpm} (rampe {self._accel_s:.1f}s) "
            f"down={self._down_s:.2f}s up={self._up_s:.2f}s",
            flush=True,
        )

    @classmethod
    def from_env(cls) -> "PiGpioNemaProbeController":
        down_s = _env_float("PROBE_NEMA_DOWN_S", 9.0)
        up_env = os.getenv("PROBE_NEMA_UP_S", "").strip()
        up_s = _env_float("PROBE_NEMA_UP_S", down_s) if up_env else None
        return cls(
            step_pin=_env_int("PROBE_NEMA_STEP_PIN", 26),
            dir_pin=_env_int("PROBE_NEMA_DIR_PIN", 27),
            steps_per_rev=_env_int("PROBE_NEMA_STEPS_PER_REV", 200),
            rpm=_env_int("PROBE_NEMA_RPM", 150),
            down_s=down_s,
            up_s=up_s,
            down_high=_direction_level(os.getenv("PROBE_NEMA_DOWN_DIR", "L"), False),
            up_high=_direction_level(os.getenv("PROBE_NEMA_UP_DIR", "H"), True),
            stabilize_s=_env_float("PROBE_STABILIZE_S", 3.0),
            start_rpm=_env_int("PROBE_NEMA_START_RPM", 50),
            accel_s=_env_float("PROBE_NEMA_ACCEL_S", 1.2),
        )

    def _delay_for_rpm(self, rpm: float) -> float:
        if rpm <= 0:
            rpm = 1.0
        delay = 60.0 / (self._steps_per_rev * rpm * 2)
        return max(delay, 0.00005)

    def _rpm_at(self, elapsed: float, total: float) -> float:
        """Profil trapézoïdal : rampe start→cruise, plateau, puis cruise→start.

        Un pas-à-pas décroche si on l'attaque directement à pleine vitesse :
        on démarre sous le couple de décrochage et on accélère/décélère en douceur.
        """
        accel = min(self._accel_s, total / 2.0)
        if accel <= 0:
            return self._rpm
        span = self._rpm - self._start_rpm
        if elapsed < accel:                          # montée en vitesse
            return self._start_rpm + span * (elapsed / accel)
        if elapsed > total - accel:                  # ralentissement avant l'arrêt
            return self._start_rpm + span * ((total - elapsed) / accel)
        return self._rpm                             # plateau

    def _rotate_for_duration(self, seconds: float, direction_high: bool, label: str) -> None:
        if seconds <= 0:
            return
        with self._lock:
            if self._closed:
                return
            GPIO = self._gpio
            GPIO.output(self._dir_pin, GPIO.HIGH if direction_high else GPIO.LOW)
            start = time.monotonic()
            steps = 0
            print(
                f"  [probe:nema] {label} {seconds:.2f}s rampe {self._start_rpm}→{self._rpm} rpm "
                f"dir={'H' if direction_high else 'L'}",
                flush=True,
            )
            while True:
                elapsed = time.monotonic() - start
                if elapsed >= seconds:
                    break
                delay = self._delay_for_rpm(self._rpm_at(elapsed, seconds))
                GPIO.output(self._step_pin, GPIO.HIGH)
                time.sleep(delay)
                GPIO.output(self._step_pin, GPIO.LOW)
                time.sleep(delay)
                steps += 1
            print(f"  [probe:nema] {label} termine ({steps} pas, avec rampe)", flush=True)

    def lower_probe(self) -> None:
        self._rotate_for_duration(self._down_s, self._down_high, "descente")

    def stabilize(self, seconds: float = 3.0) -> None:
        wait_s = self._stabilize_s if self._stabilize_s > 0 else max(0.0, seconds)
        if wait_s > 0:
            print(f"  [probe:nema] stabilisation {wait_s:.1f}s", flush=True)
            time.sleep(wait_s)

    def raise_probe(self) -> None:
        self._rotate_for_duration(self._up_s, self._up_high, "remontee")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._gpio.output(self._step_pin, self._gpio.LOW)
            self._gpio.cleanup([self._step_pin, self._dir_pin])
        except Exception:
            pass
