"""
test_sensor_hybrid.py — Mode capteur hybride (SENSOR_MODE) + valeurs aberrantes.

Couvre le scénario « essai complet sans capteur RS485 » :
  • SENSOR_MODE=mock force le capteur simulé même en APP_MODE=hardware ;
  • le mock peut injecter des profils aberrants (rate ou points forcés) ;
  • les profils aberrants restent dans les bornes physiques acceptées par le
    backend (pas de 422) mais déclenchent bien les garde-fous en aval
    (alerte salinité, qualité "suspect").
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from raspberry_pi.acquisition_manager import AcquisitionManager
from raspberry_pi.sensors.rs485_4in1 import (
    _MockSensor,
    build_sensor,
    resolve_sensor_mode,
)


class TestResolveSensorMode(unittest.TestCase):
    def test_auto_follows_app_mode(self):
        with mock.patch.dict(os.environ, {"APP_MODE": "hardware", "SENSOR_MODE": "auto"}):
            self.assertEqual(resolve_sensor_mode(), "hardware")
        with mock.patch.dict(os.environ, {"APP_MODE": "mock", "SENSOR_MODE": "auto"}):
            self.assertEqual(resolve_sensor_mode(), "mock")

    def test_sensor_mode_overrides_app_mode(self):
        with mock.patch.dict(os.environ, {"APP_MODE": "hardware", "SENSOR_MODE": "mock"}):
            self.assertEqual(resolve_sensor_mode(), "mock")

    def test_build_sensor_hybrid_returns_mock(self):
        with mock.patch.dict(os.environ, {"APP_MODE": "hardware", "SENSOR_MODE": "mock"}):
            self.assertIsInstance(build_sensor(), _MockSensor)

    def test_build_sensor_hardware_falls_back_to_mock_on_error(self):
        # Sans port série ni minimalmodbus, l'init hardware échoue → repli mock.
        env = {"APP_MODE": "hardware", "SENSOR_MODE": "hardware",
               "RS485_PORT": "/dev/inexistant-agribotics"}
        with mock.patch.dict(os.environ, env):
            self.assertIsInstance(build_sensor(), _MockSensor)


class TestMockOutliers(unittest.TestCase):
    def test_no_outlier_by_default(self):
        s = _MockSensor(seed=42)
        s.set_location("B2", 0.0, 0.0)
        self.assertIsNone(s._outlier_kind)

    def test_forced_point_is_outlier(self):
        s = _MockSensor(seed=42, outlier_points=["B2"])
        s.set_location("B2", 0.0, 0.0)
        self.assertIn(s._outlier_kind, _MockSensor.OUTLIER_PROFILES)
        s.set_location("A1", 0.0, 0.0)
        self.assertIsNone(s._outlier_kind)

    def test_rate_one_always_outlier(self):
        s = _MockSensor(seed=42, outlier_rate=1.0)
        for label in ("A1", "B2", "C3"):
            s.set_location(label, 1.0, 1.0)
            self.assertIn(s._outlier_kind, _MockSensor.OUTLIER_PROFILES)

    def test_outlier_profiles_within_backend_bounds(self):
        # Bornes de MeasurementIn : la mesure aberrante doit être ACCEPTÉE
        # par le backend pour exercer les garde-fous en aval, pas rejetée.
        for kind, (h, p, t, e) in _MockSensor.OUTLIER_PROFILES.items():
            self.assertTrue(0 <= h <= 100, kind)
            self.assertTrue(0 <= p <= 14, kind)
            self.assertTrue(-20 <= t <= 60, kind)
            self.assertTrue(0 <= e <= 20, kind)

    def test_saline_outlier_triggers_salinity_alert_threshold(self):
        _, _, _, ec = _MockSensor.OUTLIER_PROFILES["saline"]
        self.assertGreater(ec, 2.5)

    def test_canicule_outlier_yields_suspect_quality(self):
        s = _MockSensor(seed=42)
        s._outlier_kind = "canicule"
        manager = AcquisitionManager(sensor=s, interval_s=0.0, stabilization_s=0.0)
        with mock.patch.object(s, "set_location"):  # garder le profil forcé
            rec = manager.collect("B2", x=0.0, y=0.0)
        self.assertEqual(rec.quality, "suspect")

    def test_build_sensor_reads_outlier_env(self):
        env = {"APP_MODE": "mock", "SENSOR_MODE": "auto",
               "SENSOR_MOCK_OUTLIER_RATE": "0.5",
               "SENSOR_MOCK_OUTLIER_POINTS": "B2, C1"}
        with mock.patch.dict(os.environ, env):
            s = build_sensor()
        self.assertIsInstance(s, _MockSensor)
        self.assertAlmostEqual(s._outlier_rate, 0.5)
        self.assertEqual(s._outlier_points, {"B2", "C1"})


if __name__ == "__main__":
    unittest.main()
