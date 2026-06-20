"""
Tests du driver de sonde ESP32 (Esp32ProbeController), sans matériel ni pyserial.

On injecte un faux objet série (`FakeSerial`) qui rejoue des réponses scriptées
par commande. On valide le protocole : commande envoyée, attente de l'accusé
`OK`, gestion `ERR`, timeout, et lignes parasites (READY/logs) ignorées.
"""

from __future__ import annotations

import unittest

from raspberry_pi.robot.esp32_probe import Esp32ProbeController


class FakeSerial:
    """Série factice : `write(cmd)` met en file les réponses scriptées, que
    `readline()` restitue ensuite ligne par ligne (b"" = timeout série)."""

    def __init__(self, responses: dict[str, list[bytes]]):
        self.responses = responses
        self.written: list[bytes] = []
        self._inbox: list[bytes] = []
        self.closed = False

    def reset_input_buffer(self) -> None:
        self._inbox.clear()

    def write(self, data: bytes) -> None:
        self.written.append(data)
        cmd = data.decode("ascii").strip().upper()
        self._inbox.extend(self.responses.get(cmd, []))

    def flush(self) -> None:
        pass

    def readline(self) -> bytes:
        return self._inbox.pop(0) if self._inbox else b""

    def close(self) -> None:
        self.closed = True


def _probe(responses, **kw):
    return Esp32ProbeController(serial_obj=FakeSerial(responses), ack_timeout=0.3,
                               stabilize_s=0.0, **kw)


class Esp32ProbeTest(unittest.TestCase):
    def test_lower_sends_down_and_waits_ok(self) -> None:
        p = _probe({"DOWN": [b"OK\n"]})
        p.lower_probe()
        self.assertEqual(p._ser.written, [b"DOWN\n"])

    def test_raise_sends_up_and_waits_ok(self) -> None:
        p = _probe({"UP": [b"OK\n"]})
        p.raise_probe()
        self.assertEqual(p._ser.written, [b"UP\n"])

    def test_ping_true_on_ok(self) -> None:
        p = _probe({"PING": [b"OK\n"]})
        self.assertTrue(p.ping())

    def test_ping_false_on_silence(self) -> None:
        p = _probe({})                      # aucune réponse → timeout
        self.assertFalse(p.ping())

    def test_err_reply_raises(self) -> None:
        p = _probe({"DOWN": [b"ERR fault\n"]})
        with self.assertRaises(RuntimeError):
            p.lower_probe()

    def test_timeout_without_ack_raises(self) -> None:
        p = _probe({"DOWN": []})            # commande sans accusé
        with self.assertRaises(RuntimeError):
            p.lower_probe()

    def test_ignores_noise_lines_before_ok(self) -> None:
        # Messages de boot / logs avant l'accusé : ignorés, puis OK accepté.
        p = _probe({"DOWN": [b"READY\n", b"booting...\n", b"OK\n"]})
        p.lower_probe()                     # ne lève pas

    def test_close_closes_serial(self) -> None:
        p = _probe({})
        p.close()
        self.assertTrue(p._ser.closed)

    def test_stabilize_accepts_override(self) -> None:
        p = _probe({})
        p.stabilize(0.0)                    # ne bloque pas


if __name__ == "__main__":
    unittest.main()
