from __future__ import annotations

import os
import tempfile
import unittest

_TMP = tempfile.TemporaryDirectory()
os.environ["AGRIBOTICS_DB_PATH"] = os.path.join(_TMP.name, "state.sqlite3")

from fastapi.testclient import TestClient

from backend.app import app
from backend.state import APP_STATE, AppState, Measurement, MissionPoint, _hydrate_from_storage


class BackendContractsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        APP_STATE.set_plan([
            MissionPoint(label="P1", x=0.0, y=0.0),
            MissionPoint(label="P2", x=1.0, y=0.0),
        ])

    def test_plan_rejects_duplicate_labels(self) -> None:
        response = self.client.post("/api/mission/plan", json={
            "points": [
                {"label": "P1", "x": 0, "y": 0},
                {"label": "P1", "x": 1, "y": 0},
            ]
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("uniques", response.json()["detail"])

    def test_measurement_flow_and_recommendation(self) -> None:
        response = self.client.post("/api/measurements", json={
            "point": "P1",
            "humidity": 62.0,
            "ph": 6.7,
            "temp": 23.0,
            "ec": 1.1,
            "quality": "good",
        })
        self.assertEqual(response.status_code, 200)

        measurements = self.client.get("/api/measurements").json()
        self.assertEqual(measurements["latest"]["point"], "P1")
        self.assertIn("P1", measurements["by_zone"])

        recommendation = self.client.get("/api/recommendation/P1?k=3")
        self.assertEqual(recommendation.status_code, 200)
        payload = recommendation.json()
        self.assertIn(payload["engine"], {"ml", "rules"})
        self.assertGreaterEqual(len(payload["top"]), 1)
        self.assertIn("crop", payload["top"][0])

    def test_unknown_measurement_is_rejected(self) -> None:
        response = self.client.post("/api/measurements", json={
            "point": "PX",
            "humidity": 62.0,
            "ph": 6.7,
            "temp": 23.0,
            "ec": 1.1,
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("Point inconnu", response.json()["detail"])

    def test_soil_correction_contract(self) -> None:
        self.client.post("/api/measurements", json={
            "point": "P1",
            "humidity": 40.0,
            "ph": 5.5,
            "temp": 19.0,
            "ec": 2.8,
        })

        response = self.client.get("/api/recommendation/P1/correction?crop=Tomate")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["target_crop"], "Tomate")
        self.assertEqual(len(payload["diagnostics"]), 4)
        self.assertIn("actions", payload)
        self.assertIn("better_suited", payload)

    def test_state_hydrates_plan_and_measurements_from_sqlite(self) -> None:
        APP_STATE.record_measurement(Measurement(
            point="P2",
            humidity=55.0,
            ph=6.4,
            temp=22.0,
            ec=1.0,
            quality="fair",
        ))

        restored = AppState()
        _hydrate_from_storage(restored)

        self.assertEqual(restored.point_ids, ["P1", "P2"])
        self.assertEqual(restored.latest().point, "P2")
        self.assertEqual(restored.measurements_by_zone["P2"].quality, "fair")
        self.assertEqual(restored.robot.active_point, "P2")


def tearDownModule() -> None:
    _TMP.cleanup()


if __name__ == "__main__":
    unittest.main()
