"""
Contrôle d'exécution de la mission : PAUSE momentanée + reprise, et ARRÊT par
SUSPENSION (remise à l'état initial sans retour physique au départ).

On valide :
  • la traduction commande backend → décision robot (`_control_decision`) ;
  • les routes /api/mission/pause, /resume, /suspend (état + transitions).
"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

import backend.state as state
from backend.app import app
from raspberry_pi.main import _control_decision


class ControlDecisionTest(unittest.TestCase):
    def test_idle_or_abort_means_abort(self) -> None:
        self.assertEqual(_control_decision("idle"), "abort")
        self.assertEqual(_control_decision("abort"), "abort")

    def test_paused_means_pause(self) -> None:
        self.assertEqual(_control_decision("paused"), "pause")

    def test_active_commands_mean_run(self) -> None:
        for cmd in ("requested", "running", "done"):
            self.assertEqual(_control_decision(cmd), "run")

    def test_none_is_unknown_not_abort(self) -> None:
        # Backend injoignable : on ne décide rien (pas d'arrêt sur hoquet réseau,
        # pas de reprise involontaire d'une pause).
        self.assertEqual(_control_decision(None), "unknown")


class MissionControlRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        state.APP_STATE.reset()

    def _start(self) -> None:
        self.client.post("/api/mission/start")

    def test_pause_sets_command_and_status_paused(self) -> None:
        self._start()
        r = self.client.post("/api/mission/pause")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["command"], "paused")
        self.assertEqual(state.APP_STATE.robot.status, "paused")

    def test_resume_after_pause_returns_to_running(self) -> None:
        self._start()
        self.client.post("/api/mission/pause")
        r = self.client.post("/api/mission/resume")
        self.assertEqual(r.json()["command"], "running")
        self.assertEqual(state.APP_STATE.robot.status, "moving")

    def test_resume_without_pause_is_noop(self) -> None:
        self._start()                       # command == requested
        r = self.client.post("/api/mission/resume")
        self.assertEqual(r.json()["command"], "requested")

    def test_suspend_resets_to_initial_state(self) -> None:
        self._start()
        self.client.post("/api/mission/pause")
        r = self.client.post("/api/mission/suspend")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["command"], "idle")
        # État robot remis à l'initial (en attente, progression 0).
        self.assertEqual(state.APP_STATE.robot.status, "idle")
        self.assertEqual(state.APP_STATE.robot.progress_pct, 0.0)
        self.assertEqual(state.APP_STATE.measured_points, 0)

    def test_pause_ignored_when_idle(self) -> None:
        # Aucune mission en cours : la pause ne force pas un état incohérent.
        state.APP_STATE.reset()
        r = self.client.post("/api/mission/pause")
        self.assertEqual(r.json()["command"], "idle")


if __name__ == "__main__":
    unittest.main()
