"""
main.py — Orchestrateur de mission Raspberry Pi pour Agribotics.

En mode `mock` (défaut sur PC de dev) :
  • Pas de GPIO, pas de moteurs : les déplacements sont seulement loggés.
  • Le mock sensor produit des lectures cohérentes avec les profils de
    zones du frontend.

En mode `hardware` (sur le robot réel) :
  • build_sensor() instancie le driver RS485 réel (minimalmodbus + pyserial).
  • Les broches GPIO et le PCA9685 seront pilotés par robot/motors.py
    (à implémenter pour la phase 2 — non requis pour la démo logicielle).

Pour chaque point de la grille 3×3 (A1..C3) :
  1) "déplacement" (logué)
  2) acquisition_manager.collect() → MeasurementRecord
  3) push HTTP vers le backend FastAPI (POST /api/measurements)
  4) log local SQLite

Lancement :
  python3 -m raspberry_pi.main         # mission complète
  python3 -m raspberry_pi.main --point B2   # un seul point
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Iterable, List

import requests

from .acquisition_manager import AcquisitionManager, MeasurementRecord
from .sensors.rs485_4in1 import build_sensor


GRID_3X3 = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]


def _backend_url() -> str:
    return os.getenv("AGRIBOTICS_API_BASE", "http://127.0.0.1:8000").rstrip("/")


def _push_measurement(record: MeasurementRecord) -> bool:
    """Envoie la mesure au backend. Renvoie True si OK, False sinon."""
    url = f"{_backend_url()}/api/measurements"
    payload = {
        "point": record.point,
        "humidity": record.humidity,
        "ph": record.ph,
        "temp": record.temp,
        "ec": record.ec,
        "quality": record.quality,
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
        return r.status_code < 300
    except requests.RequestException:
        return False


def _move_to(point: str) -> None:
    """
    Stub de déplacement. En hardware, ce sera l'API motors.MotorController.
    En mock, on log et on simule un délai court.
    """
    print(f"  [move] → point {point}", flush=True)
    time.sleep(0.2)


def run_mission(points: Iterable[str], reset: bool = True) -> List[MeasurementRecord]:
    """Exécute la mission sur la liste de points et renvoie les records."""
    mode = os.getenv("APP_MODE", "mock").lower()
    print(f"[mission] APP_MODE={mode} | API={_backend_url()}", flush=True)

    if reset:
        try:
            requests.post(f"{_backend_url()}/api/mission/reset", timeout=3)
            print("[mission] backend reset OK", flush=True)
        except requests.RequestException:
            print("[mission] backend non joignable — on continue en local", flush=True)

    sensor = build_sensor()
    manager = AcquisitionManager(sensor=sensor, interval_s=0.0 if mode == "mock" else 0.5)
    records: List[MeasurementRecord] = []

    try:
        for p in points:
            print(f"[mission] point {p}", flush=True)
            _move_to(p)
            rec = manager.collect(p)
            records.append(rec)
            pushed = _push_measurement(rec)
            tag = "✓ pushed" if pushed else "⚠ local-only"
            print(
                f"  [meas] H={rec.humidity}%  pH={rec.ph}  T={rec.temp}°C  "
                f"EC={rec.ec} mS/cm  quality={rec.quality}  {tag}",
                flush=True,
            )
    finally:
        sensor.close()

    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Agribotics — mission Raspberry Pi")
    parser.add_argument("--point", help="Mesurer uniquement ce point (ex. B2). Sinon, mission complète 3×3.")
    parser.add_argument("--no-reset", action="store_true", help="Ne pas reset l'état mission backend avant de pousser.")
    args = parser.parse_args()

    points = [args.point] if args.point else GRID_3X3
    invalid = [p for p in points if p not in GRID_3X3]
    if invalid:
        print(f"Points invalides : {invalid}. Attendus : {GRID_3X3}", file=sys.stderr)
        return 2

    records = run_mission(points, reset=not args.no_reset)
    print(f"[mission] terminée — {len(records)} mesures collectées.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
