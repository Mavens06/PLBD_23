"""
main.py — Orchestrateur de mission Raspberry Pi pour Agribotics.

En mode `mock` (défaut sur PC de dev) :
  • Pas de GPIO, pas de moteurs : les déplacements sont seulement loggés.
  • Le mock sensor produit des lectures cohérentes (profils curés A1..C3 ou
    champ déterministe soil_at(x, y) pour des points arbitraires).

En mode `hardware` (sur le robot réel) :
  • build_sensor() instancie le driver RS485 réel (minimalmodbus + pyserial).
  • Les broches GPIO et le PCA9685 seront pilotés par robot/motors.py
    (à implémenter pour la phase 2 — non requis pour la démo logicielle).

Le PLAN de mission (liste de points {label, x, y}) est DYNAMIQUE. Par priorité :
  1) --plan plan.json   (fichier local, pratique pour tester hors interface)
  2) le backend         (GET /api/mission/plan) — défini depuis l'interface
  3) repli grille 3×3   (hors-ligne ultime)

Pour chaque point du plan :
  1) "déplacement" vers (x, y) (logué en mock)
  2) acquisition_manager.collect(label, x, y) → MeasurementRecord
  3) push HTTP vers le backend FastAPI (POST /api/measurements)

Lancements :
  python3 -m raspberry_pi.main                 # mission complète (plan backend/défaut)
  python3 -m raspberry_pi.main --point B2       # un seul point du plan
  python3 -m raspberry_pi.main --plan plan.json # plan depuis un fichier
  python3 -m raspberry_pi.main --watch          # daemon piloté par l'interface
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

import requests

from .acquisition_manager import AcquisitionManager, MeasurementRecord
from .robot import build_probe, build_robot
from .sensors.rs485_4in1 import build_sensor


# Plan 3×3 par défaut (repli hors-ligne ultime) — coordonnées en mètres.
_DEFAULT_SPACING_M = 3.0
GRID_3X3 = [
    {"label": f"{r}{c}", "x": (int(c) - 1) * _DEFAULT_SPACING_M, "y": ri * _DEFAULT_SPACING_M}
    for ri, r in enumerate("ABC")
    for c in "123"
]


@dataclass
class PlanPoint:
    label: str
    x: float
    y: float


def _backend_url() -> str:
    return os.getenv("AGRIBOTICS_API_BASE", "http://127.0.0.1:8000").rstrip("/")


def _as_points(raw: List[dict]) -> List[PlanPoint]:
    return [
        PlanPoint(label=str(p["label"]), x=float(p.get("x", 0.0)), y=float(p.get("y", 0.0)))
        for p in raw
    ]


def _load_plan_from_file(path: str) -> List[PlanPoint]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    points = data["points"] if isinstance(data, dict) else data
    return _as_points(points)


def _load_plan_from_backend() -> Optional[List[PlanPoint]]:
    try:
        r = requests.get(f"{_backend_url()}/api/mission/plan", timeout=5)
        if r.status_code < 300:
            return _as_points(r.json().get("points", []))
    except requests.RequestException:
        return None
    return None


def resolve_plan(plan_file: Optional[str]) -> List[PlanPoint]:
    """Résout le plan selon la priorité fichier → backend → grille par défaut."""
    if plan_file:
        return _load_plan_from_file(plan_file)
    backend_plan = _load_plan_from_backend()
    if backend_plan:
        return backend_plan
    print("[mission] plan backend indisponible — repli grille 3×3 par défaut", flush=True)
    return _as_points(GRID_3X3)


def _push_measurement(record: MeasurementRecord) -> bool:
    """Envoie la mesure au backend. Logge l'échec (code + corps) le cas échéant."""
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
        if r.status_code >= 300:
            # Un point silencieusement perdu fait stagner la progression :
            # on rend l'échec visible (cf. revue de code, finding #7).
            print(
                f"  [push] ⚠ échec HTTP {r.status_code} pour {record.point} : "
                f"{r.text[:200]}",
                flush=True,
            )
            return False
        return True
    except requests.RequestException as err:
        print(f"  [push] ⚠ backend injoignable pour {record.point} : {err}", flush=True)
        return False


def _fetch_command() -> Optional[str]:
    """Lit la commande mission courante du backend (None si injoignable)."""
    try:
        r = requests.get(f"{_backend_url()}/api/mission", timeout=3)
        if r.status_code < 300:
            return r.json().get("command")
    except requests.RequestException:
        return None
    return None


def run_mission(points: List[PlanPoint], reset: bool = True,
                should_abort=None) -> List[MeasurementRecord]:
    """
    Exécute la mission sur la liste de points et renvoie les records.

    Séquence par point : déplacement (robot réel ou mock) → descente sonde →
    stabilisation → acquisition capteur → remontée sonde → push backend.
    Le robot est TOUJOURS arrêté en fin de mission (finally), y compris sur
    erreur — c'est la garantie d'arrêt minimale côté robot.

    `should_abort` (optionnel) : callable renvoyant True si un arrêt d'urgence
    a été demandé. Vérifié AVANT chaque point → le robot stoppe proprement et
    n'entame pas le déplacement suivant.
    """
    mode = os.getenv("APP_MODE", "mock").lower()
    print(f"[mission] APP_MODE={mode} | API={_backend_url()} | {len(points)} point(s)", flush=True)

    if reset:
        try:
            requests.post(f"{_backend_url()}/api/mission/reset", timeout=3)
            print("[mission] backend reset OK", flush=True)
        except requests.RequestException:
            print("[mission] backend non joignable — on continue en local", flush=True)

    robot = build_robot()
    probe = build_probe()
    sensor = build_sensor()
    manager = AcquisitionManager(sensor=sensor, interval_s=0.0 if mode == "mock" else 0.5)
    records: List[MeasurementRecord] = []

    try:
        for p in points:
            if should_abort is not None and should_abort():
                print("[mission] ⛔ arrêt d'urgence demandé — mission interrompue.", flush=True)
                break
            print(f"[mission] point {p.label}", flush=True)
            robot.move_to_point(p.x, p.y)        # déplacement réel/mock
            probe.lower_probe()                  # descente de la sonde
            probe.stabilize()                    # contact sol + stabilisation
            rec = manager.collect(p.label, x=p.x, y=p.y)  # lecture capteur
            probe.raise_probe()                  # remontée avant déplacement suivant
            records.append(rec)
            pushed = _push_measurement(rec)
            tag = "✓ pushed" if pushed else "⚠ local-only"
            print(
                f"  [meas] H={rec.humidity}%  pH={rec.ph}  T={rec.temp}°C  "
                f"EC={rec.ec} mS/cm  quality={rec.quality}  {tag}",
                flush=True,
            )
    finally:
        robot.stop()
        robot.close()
        probe.close()
        sensor.close()

    return records


def watch_loop(poll_s: float = 1.5) -> int:
    """
    Mode daemon : sonde le backend et exécute le plan dès que l'interface
    demande le démarrage (command == "requested"). C'est ce qui réalise
    « l'interface commande le robot ».
    """
    print(f"[watch] en attente d'ordre de mission (poll {poll_s}s)…", flush=True)
    # `handled` empêche de relancer la mission tant qu'on n'a pas observé un
    # nouvel ordre : si une mesure échoue, le backend reste à "requested"
    # (jamais "done"), il ne faut PAS réexécuter en boucle. On ne réarme que
    # lorsque la commande repasse à autre chose que "requested" (reset/idle/done).
    handled = False
    while True:
        try:
            r = requests.get(f"{_backend_url()}/api/mission", timeout=5)
            command = r.json().get("command") if r.status_code < 300 else None
        except requests.RequestException:
            command = None

        if command == "requested" and not handled:
            handled = True
            print("[watch] ordre reçu — exécution de la mission", flush=True)
            plan = resolve_plan(None)
            # reset=False : /api/mission/start a déjà réinitialisé l'état.
            # should_abort : si la commande repasse à idle (bouton arrêt
            # d'urgence /api/mission/stop ou /end), on stoppe entre deux points.
            run_mission(
                plan, reset=False,
                should_abort=lambda: _fetch_command() in ("idle", "abort"),
            )
            print("[watch] mission terminée — retour en attente", flush=True)
        elif command != "requested":
            handled = False
        time.sleep(poll_s)


def main() -> int:
    parser = argparse.ArgumentParser(description="Agribotics — mission Raspberry Pi")
    parser.add_argument("--point", help="Mesurer uniquement ce point (label du plan, ex. B2).")
    parser.add_argument("--plan", help="Chemin d'un fichier JSON décrivant le plan (points x/y).")
    parser.add_argument("--watch", action="store_true",
                        help="Mode daemon : exécute le plan quand l'interface le demande.")
    parser.add_argument("--no-reset", action="store_true",
                        help="Ne pas reset l'état mission backend avant de pousser.")
    args = parser.parse_args()

    if args.watch:
        try:
            return watch_loop()
        except KeyboardInterrupt:
            print("\n[watch] arrêt demandé.", flush=True)
            return 0

    plan = resolve_plan(args.plan)

    if args.point:
        plan = [p for p in plan if p.label == args.point]
        if not plan:
            print(f"Point introuvable dans le plan : {args.point}", file=sys.stderr)
            return 2

    records = run_mission(plan, reset=not args.no_reset)
    print(f"[mission] terminée — {len(records)} mesures collectées.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
