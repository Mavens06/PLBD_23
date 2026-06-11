"""
rs485_4in1.py — Driver unifié du capteur agricole 4-en-1 RS485 (Modbus RTU).

Le capteur lit en un seul bloc Modbus (fonction 0x03) :
  Reg 0x0000 → moisture     × 0.1 %
  Reg 0x0001 → temperature  × 0.1 °C   (signé 16 bits)
  Reg 0x0002 → conductivity µS/cm      (converti en mS/cm)
  Reg 0x0003 → ph           × 0.1

build_sensor() retourne automatiquement :
  • _HardwareSensor (via minimalmodbus) si le mode capteur résolu est "hardware"
  • _MockSensor sinon (développement, démo, CI), ou en REPLI si l'init RS485
    échoue (port absent, lib manquante) — la mission ne plante jamais.

Le mode capteur est découplé du mode robot : SENSOR_MODE=mock avec
APP_MODE=hardware donne un robot et un bras RÉELS avec des mesures simulées —
c'est le mode « essai complet sans capteur RS485 monté ».

Variables d'environnement honorées :
  APP_MODE          : "mock" (défaut) | "hardware"
  SENSOR_MODE       : "auto" (défaut, suit APP_MODE) | "mock" | "hardware"
  RS485_PORT        : /dev/ttyUSB0 (défaut) ou /dev/ttyAMA0
  RS485_ADDRESS     : 1 (défaut)
  RS485_BAUDRATE    : 9600 (défaut)
  RS485_TIMEOUT_S   : 0.5 (défaut)
  SENSOR_MOCK_OUTLIER_RATE   : probabilité [0..1] qu'un point produise des
                               valeurs aberrantes (défaut 0 — désactivé)
  SENSOR_MOCK_OUTLIER_POINTS : labels forcés en aberrant, ex. "B2,C1"

Aucune mesure N/P/K : ce capteur ne les fournit pas.
"""

from __future__ import annotations

import math
import os
import random
import time
from dataclasses import dataclass
from typing import Optional, Protocol


def soil_at(x: float, y: float) -> tuple[float, float, float, float]:
    """
    Champ de sol synthétique DÉTERMINISTE en fonction des coordonnées (mètres).

    Renvoie (humidity %, ph, temperature °C, ec mS/cm), spatialement cohérent
    (deux points proches → valeurs proches) et borné aux plages physiques.
    Utilisé par le _MockSensor pour des points arbitraires hors des profils
    curés A1..C3.

    IMPORTANT : cette formule est dupliquée à l'identique côté frontend
    (`soilAt` dans js/data_model.js). Toute modification doit être répercutée
    des deux côtés pour que mock backend et simulation frontend restent cohérents.
    """
    humidity = 58.0 + 22.0 * math.sin(0.35 * x + 0.6) * math.cos(0.28 * y - 0.4) \
        + 3.0 * math.sin(0.9 * y)
    ph = 6.6 + 1.1 * math.sin(0.25 * x - 0.5) + 0.5 * math.cos(0.4 * y + 0.3)
    temp = 22.0 + 8.0 * math.cos(0.3 * x + 0.2) - 4.0 * math.sin(0.22 * y)
    ec = 1.4 + 1.0 * math.sin(0.4 * x + 0.9) * math.sin(0.3 * y) \
        + 0.4 * math.cos(0.5 * x)
    return (
        round(min(95.0, max(20.0, humidity)), 2),
        round(min(8.6, max(4.6, ph)), 2),
        round(min(38.0, max(8.0, temp)), 2),
        round(min(4.5, max(0.1, ec)), 3),
    )


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

    Injection de valeurs ABERRANTES (test bout-en-bout des garde-fous) :
    `outlier_rate` (probabilité par point) et/ou `outlier_points` (labels
    forcés). Les profils aberrants restent DANS les bornes physiques acceptées
    par le backend (la mesure n'est pas rejetée en 422) mais déclenchent les
    alertes en aval : salinité (EC > 2.5), sol invivable pour les 10 cultures,
    ou qualité « suspect » (valeur en bordure de plage physique).
    """

    # (humidity %, ph, temperature °C, ec mS/cm)
    OUTLIER_PROFILES = {
        "saline":   (48.0, 6.40, 24.0, 7.2),   # EC énorme → alerte salinité
        "acide":    (55.0, 3.50, 22.0, 1.2),   # pH très acide → aucune culture ok
        "sec":      (4.0,  6.80, 33.0, 1.0),   # sol quasi sec → irrigation urgente
        "canicule": (40.0, 6.60, 57.0, 1.4),   # temp en bordure → quality "suspect"
    }

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

    def __init__(self, profile: str | None = None, seed: int | None = None,
                 outlier_rate: float = 0.0,
                 outlier_points: Optional[list[str]] = None) -> None:
        self._profile = profile
        self._x: Optional[float] = None
        self._y: Optional[float] = None
        self._rng = random.Random(seed)
        self._t_last = time.monotonic()
        self._outlier_rate = max(0.0, min(1.0, outlier_rate))
        self._outlier_points = {p.strip() for p in (outlier_points or []) if p.strip()}
        self._outlier_kind: Optional[str] = None

    def set_profile(self, profile: str | None) -> None:
        """Compat ascendante : sélectionne un profil curé par label (sans coords)."""
        self.set_location(profile, None, None)

    def set_location(self, label: str | None, x: Optional[float], y: Optional[float]) -> None:
        """
        Positionne le capteur mock. Priorité au profil curé si le label est connu
        (préserve la démo A1..C3) ; sinon utilise le champ déterministe soil_at(x,y).
        """
        self._profile = label
        self._x = x
        self._y = y
        self._outlier_kind = None
        forced = label is not None and label in self._outlier_points
        drawn = self._outlier_rate > 0 and self._rng.random() < self._outlier_rate
        if forced or drawn:
            self._outlier_kind = self._rng.choice(sorted(self.OUTLIER_PROFILES))
            print(f"  [sensor:mock] ⚠ point {label} : profil aberrant injecté "
                  f"({self._outlier_kind})", flush=True)

    def _base(self) -> tuple[float, float, float, float]:
        if self._outlier_kind is not None:
            return self.OUTLIER_PROFILES[self._outlier_kind]
        if self._profile and self._profile in self.PROFILES:
            return self.PROFILES[self._profile]
        if self._x is not None and self._y is not None:
            return soil_at(self._x, self._y)
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


def resolve_sensor_mode() -> str:
    """
    Mode capteur effectif. SENSOR_MODE prime ("mock"/"hardware") ; "auto"
    (défaut) suit APP_MODE. Permet le mode hybride robot réel + capteur mock.
    """
    sensor_mode = os.getenv("SENSOR_MODE", "auto").strip().lower()
    if sensor_mode in ("mock", "hardware"):
        return sensor_mode
    return os.getenv("APP_MODE", "mock").strip().lower()


def _build_mock() -> _MockSensor:
    try:
        rate = float(os.getenv("SENSOR_MOCK_OUTLIER_RATE", "0") or 0)
    except ValueError:
        rate = 0.0
    points = [p for p in os.getenv("SENSOR_MOCK_OUTLIER_POINTS", "").split(",") if p.strip()]
    return _MockSensor(
        profile=os.getenv("SENSOR_MOCK_PROFILE"),
        outlier_rate=rate,
        outlier_points=points,
    )


def build_sensor() -> Sensor:
    """Choisit l'implémentation selon SENSOR_MODE (sinon APP_MODE)."""
    mode = resolve_sensor_mode()
    if mode == "hardware":
        try:
            port = os.getenv("RS485_PORT", "/dev/ttyUSB0")
            address = int(os.getenv("RS485_ADDRESS", "1"))
            baudrate = int(os.getenv("RS485_BAUDRATE", "9600"))
            timeout_s = float(os.getenv("RS485_TIMEOUT_S", "0.5"))
            return _HardwareSensor(port=port, address=address,
                                   baudrate=baudrate, timeout_s=timeout_s)
        except Exception as err:
            print(f"[sensor] ⚠ capteur RS485 indisponible ({err}) — repli mock.",
                  flush=True)
    elif os.getenv("APP_MODE", "mock").strip().lower() == "hardware":
        print("[sensor] SENSOR_MODE=mock — mesures simulées (robot réel).", flush=True)
    return _build_mock()
