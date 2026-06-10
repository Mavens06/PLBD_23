"""
Tests des garde-fous de sécurité ajoutés au backend :
  • validation physique des mesures (422 sur valeur aberrante) ;
  • dépendance d'authentification par clé API (opt-in).
"""

from __future__ import annotations

import unittest
from unittest import mock

from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.app as app_mod


class MeasurementValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app_mod.app)

    def test_ph_out_of_range_returns_422(self) -> None:
        r = self.client.post("/api/measurements",
                             json={"point": "A1", "humidity": 50, "ph": 999, "temp": 20, "ec": 1})
        self.assertEqual(r.status_code, 422)

    def test_negative_humidity_returns_422(self) -> None:
        r = self.client.post("/api/measurements",
                             json={"point": "A1", "humidity": -50, "ph": 6.5, "temp": 20, "ec": 1})
        self.assertEqual(r.status_code, 422)

    def test_valid_measure_is_accepted(self) -> None:
        # On définit d'abord un plan contenant le point (l'état APP_STATE est
        # partagé entre tests, donc on ne suppose pas le plan 3x3 par défaut).
        self.client.post("/api/mission/plan", json={"points": [{"label": "A1", "x": 0, "y": 0}]})
        r = self.client.post("/api/measurements",
                             json={"point": "A1", "humidity": 55, "ph": 6.4, "temp": 22, "ec": 1.1})
        self.assertEqual(r.status_code, 200)


class ApiKeyDependencyTest(unittest.TestCase):
    def test_disabled_when_no_key_configured(self) -> None:
        with mock.patch.object(app_mod, "_API_KEY", ""):
            # Ne doit pas lever, quelle que soit la valeur fournie.
            self.assertIsNone(app_mod.require_api_key(None))
            self.assertIsNone(app_mod.require_api_key("peu importe"))

    def test_enforced_when_key_configured(self) -> None:
        with mock.patch.object(app_mod, "_API_KEY", "secret"):
            self.assertIsNone(app_mod.require_api_key("secret"))      # bonne clé → ok
            with self.assertRaises(HTTPException) as ctx:
                app_mod.require_api_key("mauvaise")
            self.assertEqual(ctx.exception.status_code, 401)
            with self.assertRaises(HTTPException):
                app_mod.require_api_key(None)                          # clé manquante → 401


if __name__ == "__main__":
    unittest.main()
