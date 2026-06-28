"""
Tests du driver de sonde NEMA piloté directement par les GPIO de la Pi
(PiGpioNemaProbeController), sans matériel ni RPi.GPIO.

On injecte un faux module GPIO (`FakeGPIO`) qui enregistre les niveaux écrits.
On valide : sens DESCENTE = LOW / REMONTÉE = HIGH (sens corrigé sur le robot),
émission d'impulsions STEP, et nettoyage des broches à la fermeture.
"""

from __future__ import annotations

import unittest

from raspberry_pi.robot.nema_probe import PiGpioNemaProbeController


class FakeGPIO:
    """Module GPIO factice : constantes + journal des écritures."""

    BCM = "BCM"
    OUT = "OUT"
    HIGH = 1
    LOW = 0

    def __init__(self) -> None:
        self.mode = None
        self.setup_pins: list[int] = []
        self.writes: list[tuple[int, int]] = []
        self.cleaned = False

    def setwarnings(self, _flag) -> None:
        pass

    def setmode(self, mode) -> None:
        self.mode = mode

    def setup(self, pin, _direction) -> None:
        self.setup_pins.append(pin)

    def output(self, pin, level) -> None:
        self.writes.append((pin, level))

    def cleanup(self, _pins=None) -> None:
        self.cleaned = True

    # -- helpers de test --
    def dir_writes(self, dir_pin: int) -> list[int]:
        return [lvl for pin, lvl in self.writes if pin == dir_pin]

    def step_pulses(self, step_pin: int) -> int:
        return sum(1 for pin, lvl in self.writes if pin == step_pin and lvl == self.HIGH)


def _probe(gpio, **kw):
    # durées courtes + rampe nulle pour des tests rapides et déterministes
    params = dict(down_s=0.05, up_s=0.05, stabilize_s=0.0, accel_s=0.0, rpm=600, gpio=gpio)
    params.update(kw)
    return PiGpioNemaProbeController(**params)


class PiGpioNemaProbeTest(unittest.TestCase):
    def test_setup_configures_step_and_dir(self) -> None:
        g = FakeGPIO()
        p = _probe(g)
        self.assertEqual(g.mode, FakeGPIO.BCM)
        self.assertIn(p._step_pin, g.setup_pins)
        self.assertIn(p._dir_pin, g.setup_pins)

    def test_lower_sets_dir_low(self) -> None:
        # Sens corrigé sur le robot : DESCENTE = LOW.
        g = FakeGPIO()
        p = _probe(g)
        p.lower_probe()
        self.assertEqual(g.dir_writes(p._dir_pin)[-1], FakeGPIO.LOW)

    def test_raise_sets_dir_high(self) -> None:
        # REMONTÉE = HIGH.
        g = FakeGPIO()
        p = _probe(g)
        p.raise_probe()
        self.assertEqual(g.dir_writes(p._dir_pin)[-1], FakeGPIO.HIGH)

    def test_lower_emits_step_pulses(self) -> None:
        g = FakeGPIO()
        p = _probe(g)
        p.lower_probe()
        self.assertGreater(g.step_pulses(p._step_pin), 0)

    def test_zero_duration_no_pulses(self) -> None:
        g = FakeGPIO()
        p = _probe(g, down_s=0.0)
        p.lower_probe()
        self.assertEqual(g.step_pulses(p._step_pin), 0)

    def test_stabilize_override_no_block(self) -> None:
        g = FakeGPIO()
        p = _probe(g)
        p.stabilize(0.0)                    # ne bloque pas

    def test_close_parks_safe_without_cleanup(self) -> None:
        # close() NE doit PAS remettre les broches en entrée (cleanup) : une
        # STEP flottante sur un A4988 toujours actif (EN=GND) capte du bruit →
        # descente parasite après la mission. Park sûr attendu : DIR en remontée
        # (HIGH), STEP à LOW, et AUCUN cleanup.
        g = FakeGPIO()
        p = _probe(g)
        g.writes.clear()
        p.close()
        self.assertFalse(g.cleaned)
        self.assertEqual(g.dir_writes(p._dir_pin)[-1], FakeGPIO.HIGH)
        last_step = [lvl for pin, lvl in g.writes if pin == p._step_pin][-1]
        self.assertEqual(last_step, FakeGPIO.LOW)

    def test_ramp_profile_bounds(self) -> None:
        # Au repos -> start_rpm ; au milieu -> cruise ; jamais au-delà du cruise.
        g = FakeGPIO()
        p = _probe(g, accel_s=1.0, start_rpm=50, rpm=150, down_s=4.0)
        self.assertAlmostEqual(p._rpm_at(0.0, 4.0), 50, delta=1)
        self.assertAlmostEqual(p._rpm_at(2.0, 4.0), 150, delta=1)
        self.assertLessEqual(p._rpm_at(1.0, 4.0), 150)


if __name__ == "__main__":
    unittest.main()
