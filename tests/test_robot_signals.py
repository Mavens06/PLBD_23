"""
test_robot_signals.py — Dégradation douce des LEDs/buzzer (signals.py).

Sur PC de dev (pas de gpiozero/GPIO), MissionSignals doit s'instancier et
toutes ses méthodes doivent être des no-ops silencieux : une LED absente ne
doit JAMAIS faire échouer une mission.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from raspberry_pi.robot.signals import MissionSignals


class TestMissionSignalsFallback(unittest.TestCase):
    def test_all_methods_are_safe_without_hardware(self):
        s = MissionSignals()
        # Aucune de ces méthodes ne doit lever, même sans gpiozero/broches.
        s.beep("C4", 0.0)
        s.blink(0.0)
        s.alert_on()
        s.alert_off()
        s.close()

    def test_disabled_via_env(self):
        with mock.patch.dict(os.environ, {"SIGNALS_ENABLED": "0"}):
            s = MissionSignals()
        self.assertEqual(s._leds, [])
        self.assertIsNone(s._buzzer)
        s.beep()
        s.blink()
        s.close()


if __name__ == "__main__":
    unittest.main()
