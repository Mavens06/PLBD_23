"""
esp32_sensor.py — Lecture TEMPÉRATURE + HUMIDITÉ depuis un ESP32 en USB série.

L'ESP32 (DS18B20 1-Wire + capteur d'humidité capacitif sur ADC) émet en clair,
toutes les ~2 s, une trame texte :

    Température : 24.81 °C, Humidité : 53.16 %

La Raspberry Pi lit ce flux via le port USB (puce CP2102, débit 115200).

POINT CRUCIAL — ouvrir le port en laissant **DTR et RTS au repos**
(`dtr=False, rts=False`). Sinon le CP2102 force un RESET de l'ESP32 à chaque
ouverture : on ne capte alors que les messages de boot ROM (à 74880 baud, donc
illisibles à 115200) au lieu des trames du sketch. C'est exactement le piège
qui faisait croire à un « port muet » lors de la mise au point.

Un thread de fond maintient en continu la DERNIÈRE valeur reçue ; `latest()` la
renvoie sans bloquer. Conçu pour être COMBINÉ à un capteur de base (RS485 ou
mock) qui synthétise pH + EC à partir de ces valeurs réelles
(cf. `_Esp32SoilSensor` et `SoilSynthesizer` dans soil_sensor.py).
"""

from __future__ import annotations

import re
import threading
import time
from typing import Optional, Tuple

# Tolérant : 'Température'/'Temp', deux-points, virgule OU point décimal, signe.
# Le cas « Erreur » (DS18B20 déconnectée) ne matche aucun nombre → None.
_RE_TEMP = re.compile(r"emp[^:]*:\s*(-?\d+(?:[.,]\d+)?)", re.IGNORECASE)
_RE_HUM = re.compile(r"umid[^:]*:\s*(-?\d+(?:[.,]\d+)?)", re.IGNORECASE)


def parse_line(line: str) -> Tuple[Optional[float], Optional[float]]:
    """Extrait (température °C, humidité %) d'une trame ESP32.

    Renvoie un tuple (temp, hum) où chaque membre vaut None s'il est absent ou
    illisible (ex. « Température : Erreur » → temp=None). Fonction PURE, testée
    sans matériel.
    """
    mt = _RE_TEMP.search(line)
    mh = _RE_HUM.search(line)
    temp = float(mt.group(1).replace(",", ".")) if mt else None
    hum = float(mh.group(1).replace(",", ".")) if mh else None
    return temp, hum


class Esp32Sensor:
    """Lecteur série non bloquant du flux température/humidité de l'ESP32."""

    def __init__(self, port: str, baudrate: int = 115200, timeout_s: float = 2.0) -> None:
        import serial  # import paresseux : pyserial n'est requis que sur la Pi

        self._serial = serial
        self._port = port
        self._baud = baudrate
        self._timeout = timeout_s
        self._ser = None
        self._lock = threading.Lock()
        self._temp: Optional[float] = None
        self._hum: Optional[float] = None
        self._ts: float = 0.0          # monotonic de la dernière trame valide
        self._stop = threading.Event()

        self._open()
        self._thread = threading.Thread(
            target=self._loop, name="esp32-reader", daemon=True)
        self._thread.start()

    # -- liaison série -------------------------------------------------------

    def _open(self) -> None:
        """Ouvre le port SANS toucher DTR/RTS (sinon reset de l'ESP32)."""
        ser = self._serial.Serial()
        ser.port = self._port
        ser.baudrate = self._baud
        ser.timeout = self._timeout
        ser.dtr = False
        ser.rts = False
        ser.open()
        try:
            ser.reset_input_buffer()
        except Exception:
            pass
        self._ser = ser

    def _reconnect(self) -> None:
        try:
            if self._ser:
                self._ser.close()
        except Exception:
            pass
        time.sleep(1.0)
        try:
            self._open()
        except Exception:
            pass  # on réessaiera au prochain tour de boucle

    # -- boucle de lecture ---------------------------------------------------

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                raw = self._ser.readline()
            except Exception:
                if self._stop.is_set():
                    break
                self._reconnect()
                continue
            if not raw:
                continue
            temp, hum = parse_line(raw.decode("utf-8", "replace"))
            if temp is None and hum is None:
                continue
            with self._lock:
                if temp is not None:
                    self._temp = temp
                if hum is not None:
                    self._hum = hum
                self._ts = time.monotonic()

    # -- API -----------------------------------------------------------------

    def latest(self) -> Tuple[Optional[float], Optional[float]]:
        """Dernières (température, humidité) reçues, ou (None, None) si rien encore."""
        with self._lock:
            return self._temp, self._hum

    def wait_first(self, timeout_s: float = 6.0) -> bool:
        """Bloque jusqu'à la première trame valide (ou timeout). True si reçue."""
        deadline = time.monotonic() + max(0.0, timeout_s)
        while time.monotonic() < deadline:
            with self._lock:
                if self._ts > 0:
                    return True
            if self._stop.is_set():
                return False
            time.sleep(0.1)
        with self._lock:
            return self._ts > 0

    def close(self) -> None:
        self._stop.set()
        try:
            if self._ser:
                self._ser.close()
        except Exception:
            pass
