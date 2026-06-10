"""
Tests de la file d'attente hors-ligne du robot (résilience réseau au champ).

Garantit qu'aucune mesure n'est perdue quand le backend est injoignable :
la mesure est persistée puis retransmise au flush suivant.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from raspberry_pi.offline_buffer import OfflineBuffer


class OfflineBufferTest(unittest.TestCase):
    def _buf(self, td: str) -> OfflineBuffer:
        return OfflineBuffer(Path(td) / "outbox.jsonl")

    def test_enqueue_increments_pending(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            b = self._buf(td)
            self.assertEqual(b.pending(), 0)
            b.enqueue({"point": "P1"})
            b.enqueue({"point": "P2"})
            self.assertEqual(b.pending(), 2)

    def test_flush_all_success_empties_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            b = self._buf(td)
            b.enqueue({"point": "P1"})
            b.enqueue({"point": "P2"})
            sent = b.flush(lambda payload: True)
            self.assertEqual(sent, 2)
            self.assertEqual(b.pending(), 0)

    def test_flush_all_fail_keeps_everything(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            b = self._buf(td)
            b.enqueue({"point": "P1"})
            b.enqueue({"point": "P2"})
            sent = b.flush(lambda payload: False)
            self.assertEqual(sent, 0)
            self.assertEqual(b.pending(), 2)

    def test_flush_stops_at_first_failure(self) -> None:
        # P1 transmis, P2 échoue → on garde P2 et la suite (pas de martèlement réseau).
        with tempfile.TemporaryDirectory() as td:
            b = self._buf(td)
            for pt in ("P1", "P2", "P3"):
                b.enqueue({"point": pt})
            sent = b.flush(lambda payload: payload["point"] == "P1")
            self.assertEqual(sent, 1)
            self.assertEqual(b.pending(), 2)

    def test_push_exception_is_treated_as_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            b = self._buf(td)
            b.enqueue({"point": "P1"})

            def boom(_payload):
                raise RuntimeError("réseau")

            sent = b.flush(boom)
            self.assertEqual(sent, 0)
            self.assertEqual(b.pending(), 1)

    def test_corrupt_line_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            b = self._buf(td)
            b.path.parent.mkdir(parents=True, exist_ok=True)
            b.path.write_text('{"point": "P1"}\nPAS_DU_JSON\n{"point": "P2"}\n', encoding="utf-8")
            self.assertEqual(b.pending(), 2)          # la ligne illisible est ignorée
            sent = b.flush(lambda payload: True)
            self.assertEqual(sent, 2)

    def test_flush_empty_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            b = self._buf(td)
            self.assertEqual(b.flush(lambda payload: True), 0)


if __name__ == "__main__":
    unittest.main()
