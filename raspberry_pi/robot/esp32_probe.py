"""
esp32_probe.py — Pilotage de la sonde (NEMA) via un ESP32 relié en USB série.

La descente/remontée de la sonde n'est plus assurée par un servo du PiCar-Pro
mais par un **moteur pas-à-pas NEMA piloté par un ESP32**. La Raspberry Pi parle
à l'ESP32 par **USB série** avec un protocole texte minimal, à accusé de
réception (l'ESP32 confirme la fin RÉELLE du mouvement) :

    Pi → ESP32 : "DOWN\\n"   (descendre la sonde dans le sol)
    ESP32 → Pi : "OK\\n"     (mouvement terminé)
    Pi → ESP32 : "UP\\n"     (remonter la sonde)
    ESP32 → Pi : "OK\\n"
    Pi → ESP32 : "PING\\n"   (test de présence) → "OK\\n"
    Pi → ESP32 : "OFF\\n"    (couper le driver si EN est câblé) → "OK\\n"
    (en cas d'erreur côté ESP32 : "ERR ...\\n")

`lower_probe()` / `raise_probe()` BLOQUENT jusqu'à l'accusé `OK` (ou lèvent une
RuntimeError au timeout) : la mesure n'a donc jamais lieu avant que la sonde soit
réellement au contact du sol. Le firmware peut couper le driver après `UP` si
la broche EN du driver est câblée sur l'ESP32. C'est l'équivalent ESP32 d'`AdeeptProbeController`
— même interface `ProbeController`, donc l'orchestrateur de mission est inchangé.

Le firmware ESP32 correspondant est dans `deploy/esp32_probe/esp32_probe.ino`.
"""

from __future__ import annotations

import time

from .base import ProbeController


class Esp32ProbeController(ProbeController):
    """Sonde NEMA pilotée par un ESP32 en USB série (protocole DOWN/UP + OK)."""

    def __init__(
        self,
        port: str = "/dev/ttyACM0",
        baud: int = 115200,
        ack_timeout: float = 15.0,
        stabilize_s: float = 3.0,
        boot_wait_s: float = 2.0,
        serial_obj=None,
    ) -> None:
        """
        Paramètres
        ----------
        port : chemin série de l'ESP32 (préférer un chemin stable
               `/dev/serial/by-id/...` pour ne pas le confondre avec le capteur
               RS485, lui aussi en USB série).
        baud : débit série (doit correspondre au `Serial.begin()` du firmware).
        ack_timeout : délai max d'attente de l'accusé `OK` (s) — borne haute de la
               course de la sonde.
        stabilize_s : attente de stabilisation après descente (contact sol/sonde).
        boot_wait_s : à l'ouverture du port, l'ESP32 redémarre (auto-reset
               DTR/RTS) ; on attend son boot puis on purge le tampon.
        serial_obj : objet série déjà ouvert (injection pour les tests) ; si
               fourni, `port`/`baud`/`boot_wait_s` sont ignorés.
        """
        self._stabilize_s = float(stabilize_s)
        self._ack_timeout = float(ack_timeout)

        if serial_obj is not None:
            self._ser = serial_obj
            return

        # Import paresseux : pyserial n'est requis que sur le robot réel.
        import serial  # type: ignore

        self._ser = serial.Serial(port, baud, timeout=1.0)
        # L'ouverture du port provoque le reset de l'ESP32 → on laisse booter,
        # puis on vide les messages de démarrage (ex. "READY").
        time.sleep(max(0.0, float(boot_wait_s)))
        try:
            self._ser.reset_input_buffer()
        except Exception:
            pass

    # -- Protocole -----------------------------------------------------------
    def _command(self, cmd: str) -> None:
        """Envoie une commande et BLOQUE jusqu'à l'accusé `OK` (ou RuntimeError)."""
        try:
            self._ser.reset_input_buffer()
        except Exception:
            pass
        self._ser.write((cmd + "\n").encode("ascii"))
        try:
            self._ser.flush()
        except Exception:
            pass

        deadline = time.time() + self._ack_timeout
        while time.time() < deadline:
            raw = self._ser.readline()              # bloque jusqu'au timeout série (~1 s)
            if not raw:
                continue
            line = raw.decode("ascii", errors="ignore").strip().upper()
            if not line:
                continue
            if line.startswith("OK"):
                return
            if line.startswith("ERR"):
                raise RuntimeError(f"ESP32 sonde : erreur sur '{cmd}' → {line}")
            # autres lignes (logs/READY) : on les ignore et on continue d'attendre
        raise RuntimeError(
            f"ESP32 sonde : pas d'accusé 'OK' pour '{cmd}' en {self._ack_timeout:.0f} s "
            "(ESP32 débranché, mauvais port, ou firmware absent ?)."
        )

    def ping(self) -> bool:
        """Teste la présence de l'ESP32 (True si 'OK' reçu)."""
        try:
            self._command("PING")
            return True
        except RuntimeError:
            return False

    # -- Interface ProbeController ------------------------------------------
    def lower_probe(self) -> None:
        self._command("DOWN")

    def raise_probe(self) -> None:
        self._command("UP")

    def stabilize(self, seconds: float | None = None) -> None:
        time.sleep(self._stabilize_s if seconds is None else float(seconds))

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:
            pass
