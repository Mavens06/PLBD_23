"""
soil_sensor.py — Capteur de sol unifié Agribotics (sans RS485).

Architecture d'acquisition (plus AUCUN capteur RS485) :
  • TEMPÉRATURE + HUMIDITÉ → lues en RÉEL sur un ESP32 en USB série
    (DS18B20 1-Wire + capteur d'humidité capacitif), cf. esp32_sensor.py.
  • pH + EC → GÉNÉRÉS de façon agronomiquement cohérente À PARTIR de
    l'humidité et de la température réelles (SoilSynthesizer), avec une légère
    dérive temporelle (marche aléatoire lissée) pour un rendu « temps réel »
    crédible. Aucune valeur n'est tirée au hasard de façon absurde : pH et EC
    suivent des relations physiques connues (EC ↑ avec l'eau et la température,
    pH légèrement plus acide en sol humide…).

build_sensor() retourne automatiquement :
  • _Esp32SoilSensor si le mode est `hardware` ET un ESP32 est branché
    (ESP32_SENSOR_PORT défini) : température + humidité réelles, pH + EC
    synthétisés à partir d'elles.
  • _MockSensor sinon (dev / démo / CI, ou repli si l'ESP32 est absent) :
    champ de sol déterministe soil_at(x, y) + profils curés A1..C3 — mêmes
    valeurs que le frontend de simulation.

Aucune mesure N/P/K : hors périmètre du projet (capteur inexistant).
"""

from __future__ import annotations

import math
import os
import random
import time
from dataclasses import dataclass
from typing import Optional, Protocol


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


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
    """Une lecture du capteur de sol (4 variables : humidité, temp, EC, pH)."""
    humidity: float        # %
    temperature: float     # °C
    ec: float              # mS/cm
    ph: float              # unités de pH

    def as_dict(self) -> dict:
        return {"humidity": self.humidity, "temperature": self.temperature,
                "ec": self.ec, "ph": self.ph}


class Sensor(Protocol):
    """Interface commune des implémentations de capteur."""
    def read(self) -> SensorReading: ...
    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# Générateur pH / EC corrélé à l'humidité + température RÉELLES
# ---------------------------------------------------------------------------

class SoilSynthesizer:
    """
    Génère un couple (pH, EC) AGRONOMIQUEMENT cohérent à partir de l'humidité
    et de la température réelles lues, avec une légère dérive temporelle lissée
    (marche aléatoire bornée) pour un rendu « temps réel » naturel.

    Relations modélisées (déterministes, défendables) :
      • EC ↑ avec l'humidité : l'eau du sol porte le courant → un sol plus
        humide conduit davantage (EC volumique). Forme ec_base = a + b·(H/100)^n.
      • EC ↑ avec la température : compensation classique ≈ +1,9 %/°C autour de
        25 °C (mobilité ionique).
      • pH légèrement plus ACIDE en sol humide (lessivage, acides organiques) et
        un effet thermique faible. Reste dans une plage de sol cultivable.

    Le bruit ajouté est petit (capteur réaliste), la dérive est lente et bornée
    pour que deux lectures successives soient proches (faible écart-type → la
    qualité d'acquisition reste « good »).
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._ph_drift = 0.0
        self._ec_drift = 0.0

    def synthesize(self, humidity: Optional[float],
                   temperature: Optional[float]) -> tuple[float, float]:
        # Replis prudents si l'ESP32 n'a pas encore de valeur.
        h = _clamp(humidity if humidity is not None else 55.0, 0.0, 100.0)
        t = _clamp(temperature if temperature is not None else 22.0, -10.0, 60.0)

        # Dérive douce et bornée (évolution naturelle entre deux points).
        self._ph_drift = _clamp(self._ph_drift + self._rng.gauss(0, 0.010), -0.25, 0.25)
        self._ec_drift = _clamp(self._ec_drift + self._rng.gauss(0, 0.010), -0.20, 0.20)

        # pH : base proche de la neutralité, plus acide en sol humide, effet temp faible.
        ph = 6.85 - 0.70 * (h / 100.0 - 0.50) - 0.012 * (t - 22.0)
        ph += self._ph_drift + self._rng.gauss(0, 0.03)
        ph = _clamp(ph, 5.3, 7.9)

        # EC : croît avec l'humidité (conduction par l'eau) + compensation thermique.
        ec_base = 0.45 + 1.90 * (h / 100.0) ** 1.30
        temp_comp = 1.0 + 0.019 * (t - 25.0)
        ec = ec_base * temp_comp + self._ec_drift + self._rng.gauss(0, 0.04)
        ec = _clamp(ec, 0.15, 4.5)

        return round(ph, 2), round(ec, 3)


class _Esp32SoilSensor:
    """
    Capteur de sol RÉEL avec REPLI AUTOMATIQUE en simulation.

    Cas nominal : température + humidité de l'ESP32, pH + EC synthétisés à
    partir de ces valeurs réelles (SoilSynthesizer).

    Cas dégradé : si l'acquisition ESP32 a un problème (débranché, muet, trames
    obsolètes, ou DS18B20 en « Erreur » → cf. `Esp32Sensor.is_fresh`), chaque
    lecture **bascule automatiquement sur le capteur mock** (`fallback`) qui
    produit des valeurs cohérentes — la mission continue sans valeur figée ni
    plantage. Dès que l'ESP32 réémet des trames fraîches, on **reprend** les
    mesures réelles. Les bascules aller/retour sont journalisées une seule fois.
    """

    def __init__(self, esp32, synthesizer: SoilSynthesizer, fallback: Sensor,
                 stale_after_s: float = 8.0) -> None:
        self._esp32 = esp32
        self._synth = synthesizer
        self._fallback = fallback
        self._stale_after = max(0.5, stale_after_s)
        self._degraded = False
        self._last_t = 22.0
        self._last_h = 55.0

    def set_location(self, label: str | None, x: Optional[float], y: Optional[float]) -> None:
        # Toujours positionner le mock de secours pour qu'il soit prêt (valeurs
        # cohérentes avec la zone) en cas de bascule.
        if hasattr(self._fallback, "set_location"):
            self._fallback.set_location(label, x, y)

    def set_profile(self, profile: str | None) -> None:
        if hasattr(self._fallback, "set_profile"):
            self._fallback.set_profile(profile)

    def read(self) -> SensorReading:
        if not self._esp32.is_fresh(self._stale_after):
            if not self._degraded:
                print("[sensor] ⚠ acquisition ESP32 en panne (muette/obsolète) "
                      "→ bascule automatique en SIMULATION (mock).", flush=True)
                self._degraded = True
            return self._fallback.read()

        if self._degraded:
            print("[sensor] ✅ ESP32 de nouveau actif → reprise des mesures réelles.",
                  flush=True)
            self._degraded = False

        t, h = self._esp32.latest()
        if t is not None:
            self._last_t = t
        if h is not None:
            self._last_h = h
        ph, ec = self._synth.synthesize(self._last_h, self._last_t)
        return SensorReading(
            humidity=round(self._last_h, 2),
            temperature=round(self._last_t, 2),
            ec=ec,
            ph=ph,
        )

    def close(self) -> None:
        try:
            self._esp32.close()
        finally:
            if hasattr(self._fallback, "close"):
                self._fallback.close()


# ---------------------------------------------------------------------------
# Capteur simulé (dev / démo / CI) — inchangé
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Sélection de l'implémentation
# ---------------------------------------------------------------------------

def resolve_sensor_mode() -> str:
    """
    Mode capteur effectif. SENSOR_MODE prime ("mock"/"hardware") ; "auto"
    (défaut) suit APP_MODE. Permet de forcer la simulation même sur le robot.
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
    """
    Point d'entrée unique.

    • mode hardware + ESP32 branché (ESP32_SENSOR_PORT) → capteur RÉEL :
      température + humidité de l'ESP32, pH + EC synthétisés à partir d'elles.
    • sinon → capteur simulé (_MockSensor). Repli automatique si l'ESP32 est
      absent ou pyserial manquant : la mission ne plante jamais.
    """
    mode = resolve_sensor_mode()
    port = os.getenv("ESP32_SENSOR_PORT", "").strip()

    if mode == "hardware" and port:
        try:
            from .esp32_sensor import Esp32Sensor
            baud = int(os.getenv("ESP32_SENSOR_BAUD", "115200"))
            warmup = float(os.getenv("ESP32_SENSOR_WARMUP_S", "6"))
            stale_after = float(os.getenv("ESP32_SENSOR_STALE_S", "8"))
            esp = Esp32Sensor(port, baudrate=baud)
            got = esp.wait_first(timeout_s=warmup)
            # Mock de secours : repli automatique si l'ESP32 tombe en panne.
            sensor = _Esp32SoilSensor(esp, SoilSynthesizer(), _build_mock(),
                                      stale_after_s=stale_after)
            if got:
                t, h = esp.latest()
                print(f"[sensor] ESP32 {port} OK — temp={t} °C, humidité={h} % "
                      f"(pH + EC synthétisés à partir de ces valeurs réelles).",
                      flush=True)
            else:
                print(f"[sensor] ⚠ ESP32 {port} : aucune trame en {warmup:.0f}s "
                      f"(branchement ? DTR ?) — valeurs dès réception.", flush=True)
            return sensor
        except Exception as err:
            print(f"[sensor] ⚠ ESP32 indisponible ({err}) — repli simulation.",
                  flush=True)
    elif mode == "hardware":
        print("[sensor] mode hardware sans ESP32_SENSOR_PORT — simulation (mock).",
              flush=True)

    return _build_mock()
