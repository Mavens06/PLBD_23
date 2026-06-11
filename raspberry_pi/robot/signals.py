"""
signals.py — LEDs + buzzer de signalisation du PiCar-Pro (gpiozero).

Broches VALIDÉES sur le robot (Code_PLBD_23_mission.py) :
  • LEDs    : GPIO 25 et 11
  • Buzzer  : GPIO 18 (TonalBuzzer)

Utilisé par AdeeptRobotController pour rendre la mission lisible pendant la
démo : bip au démarrage, clignotement à chaque point atteint, bip + LED sur
obstacle, bip aigu en fin de mission.

DÉGRADATION DOUCE : si gpiozero ou les broches sont indisponibles (PC de dev,
périphérique débranché), chaque sortie devient un no-op silencieux — la
mission n'échoue JAMAIS à cause d'une LED. Désactivable via SIGNALS_ENABLED=0.
"""

from __future__ import annotations

import os
import time


def _log(msg: str) -> None:
    print(f"  [robot:signals] {msg}", flush=True)


def _envi(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


class MissionSignals:
    """LEDs + buzzer, chaque périphérique initialisé indépendamment."""

    def __init__(self) -> None:
        self._leds = []
        self._buzzer = None
        if os.getenv("SIGNALS_ENABLED", "1").strip().lower() not in ("1", "true", "yes"):
            return
        led_pins_raw = os.getenv("LED_PINS", "25,11")
        for raw in led_pins_raw.split(","):
            if not raw.strip():
                continue
            try:
                from gpiozero import LED
                self._leds.append(LED(int(raw.strip())))
            except Exception as err:
                _log(f"⚠ LED GPIO {raw.strip()} indisponible ({err}) — ignorée.")
        try:
            from gpiozero import TonalBuzzer
            self._buzzer = TonalBuzzer(_envi("BUZZER_PIN", 18))
        except Exception as err:
            _log(f"⚠ buzzer indisponible ({err}) — ignoré.")

    def beep(self, note: str = "C4", duration: float = 0.25) -> None:
        if self._buzzer is None:
            return
        try:
            self._buzzer.play(note)
            time.sleep(max(0.0, duration))
            self._buzzer.stop()
        except Exception:
            pass

    def blink(self, duration: float = 0.3) -> None:
        if not self._leds:
            return
        try:
            for led in self._leds:
                led.on()
            time.sleep(max(0.0, duration))
            for led in self._leds:
                led.off()
        except Exception:
            pass

    def alert_on(self) -> None:
        """LED d'alerte allumée en continu (obstacle)."""
        if self._leds:
            try:
                self._leds[0].on()
            except Exception:
                pass

    def alert_off(self) -> None:
        if self._leds:
            try:
                self._leds[0].off()
            except Exception:
                pass

    def close(self) -> None:
        try:
            self.alert_off()
            if self._buzzer is not None:
                self._buzzer.stop()
            for led in self._leds:
                led.close()
            if self._buzzer is not None:
                self._buzzer.close()
        except Exception:
            pass
