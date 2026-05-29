"""
rs485_4in1.py — Driver unifié du capteur agricole 4-en-1 RS485 (Modbus RTU).

Le capteur lit en un seul bloc Modbus (fonction 0x03) :
  Reg 0x0000 → moisture     × 0.1 %
  Reg 0x0001 → temperature  × 0.1 °C   (signé 16 bits)
  Reg 0x0002 → conductivity µS/cm      (converti en mS/cm)
  Reg 0x0003 → ph           × 0.1

build_sensor() retourne automatiquement :
  • _HardwareSensor (via minimalmodbus) si APP_MODE=hardware
  • _MockSensor sinon (développement, démo, CI)

Variables d'environnement honorées :
  APP_MODE          : "mock" (défaut) | "hardware"
  RS485_PORT        : /dev/ttyUSB0 (défaut) ou /dev/ttyAMA0
  RS485_ADDRESS     : 1 (défaut)
  RS485_BAUDRATE    : 9600 (défaut)
  RS485_TIMEOUT_S   : 0.5 (défaut)

Aucune mesure N/P/K : ce capteur ne les fournit pas.
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from typing import Protocol


@dataclass
class SensorReading:
    """Une lecture brute du capteur 4-en-1."""
    humidity: float        # %
    temperature: float     # °C
    ec: float              # mS/cm (déjà converti depuis µS/cm)
    ph: float              # unités de pH

    def as_dict(self) -> dict:
        return {"humidity": self.humidity, "temperature": self.temperature,
                "ec": self.ec, "ph": self.ph}


class Sensor(Protocol):
    """Interface commune des deux implémentations."""
    def read(self) -> SensorReading: ...
    def close(self) -> None: ...


def _twos_complement(value: int, bits: int = 16) -> int:
    """Convertit une lecture Modbus 16 bits non-signée en signée."""
    if value >= (1 << (bits - 1)):
        return value - (1 << bits)
    return value


class _HardwareSensor:
    """Lecture réelle via minimalmodbus (RTU sur USB-Serial)."""

    REG_BLOCK_START = 0x0000
    REG_COUNT = 4

    def __init__(
        self,
        port: str,
        address: int,
        baudrate: int = 9600,
        timeout_s: float = 0.5,
    ) -> None:
        # Import paresseux pour ne PAS imposer la dépendance hors Pi.
        import minimalmodbus
        import serial

        self._instrument = minimalmodbus.Instrument(port, address)
        self._instrument.serial.baudrate = baudrate
        self._instrument.serial.bytesize = 8
        self._instrument.serial.parity = serial.PARITY_NONE
        self._instrument.serial.stopbits = 1
        self._instrument.serial.timeout = timeout_s
        self._instrument.mode = minimalmodbus.MODE_RTU

    def read(self) -> SensorReading:
        regs = self._instrument.read_registers(
            self.REG_BLOCK_START, self.REG_COUNT, functioncode=3,
        )
        humidity_raw, temp_raw, cond_raw, ph_raw = regs
        return SensorReading(
            humidity=humidity_raw * 0.1,
            temperature=_twos_complement(temp_raw) * 0.1,
            ec=cond_raw / 1000.0,             # µS/cm → mS/cm
            ph=ph_raw * 0.1,
        )

    def close(self) -> None:
        try:
            self._instrument.serial.close()
        except Exception:
            pass


class _MockSensor:
    """
    Sensor simulé pour le dev et la démo.

    Si SENSOR_MOCK_PROFILE est fourni (ex. "B2"), retourne un signal centré
    sur le profil correspondant à la zone (mêmes valeurs que le frontend
    simulation). Sinon, oscille autour de valeurs raisonnables.
    """

    PROFILES = {
        "A1": (32.0, 5.40, 34.0, 2.8),
        "A2": (52.0, 6.05, 22.0, 1.1),
        "A3": (88.0, 7.90, 20.0, 0.5),
        "B1": (41.0, 6.80, 31.0, 1.8),
        "B2": (63.0, 5.65, 24.0, 0.9),
        "B3": (75.0, 7.35, 13.0, 2.2),
        "C1": (90.0, 8.15, 36.0, 3.1),
        "C2": (70.0, 6.70, 10.0, 1.5),
        "C3": (56.0, 7.18, 26.0, 0.7),
    }

    def __init__(self, profile: str | None = None, seed: int | None = None) -> None:
        self._profile = profile
        self._rng = random.Random(seed)
        self._t_last = time.monotonic()

    def set_profile(self, profile: str | None) -> None:
        self._profile = profile

    def _base(self) -> tuple[float, float, float, float]:
        if self._profile and self._profile in self.PROFILES:
            return self.PROFILES[self._profile]
        return (58.0, 6.5, 22.0, 1.0)

    def read(self) -> SensorReading:
        # Léger jitter pour simuler du bruit capteur.
        h, p, t, e = self._base()
        return SensorReading(
            humidity=round(max(0.0, h + self._rng.gauss(0, 1.4)), 2),
            ph=round(max(0.0, p + self._rng.gauss(0, 0.05)), 2),
            temperature=round(t + self._rng.gauss(0, 0.4), 2),
            ec=round(max(0.0, e + self._rng.gauss(0, 0.08)), 3),
        )

    def close(self) -> None:
        return None


def build_sensor() -> Sensor:
    """Choisit l'implémentation selon APP_MODE."""
    mode = os.getenv("APP_MODE", "mock").strip().lower()
    if mode == "hardware":
        port = os.getenv("RS485_PORT", "/dev/ttyUSB0")
        address = int(os.getenv("RS485_ADDRESS", "1"))
        baudrate = int(os.getenv("RS485_BAUDRATE", "9600"))
        timeout_s = float(os.getenv("RS485_TIMEOUT_S", "0.5"))
        return _HardwareSensor(port=port, address=address,
                               baudrate=baudrate, timeout_s=timeout_s)
    # mock par défaut
    return _MockSensor(profile=os.getenv("SENSOR_MOCK_PROFILE"))
