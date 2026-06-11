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
from dotenv import load_dotenv

# Même .env que le backend (racine du dépôt). Les variables déjà exportées
# dans le shell gardent la priorité (load_dotenv n'écrase pas l'existant) —
# indispensable pour que SENSOR_MODE, PROBE_SERVO_CHANNEL, ROBOT_SPEED_MPS…
# configurés dans .env soient vus par le processus robot (pas seulement le backend).
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from .acquisition_manager import AcquisitionManager, MeasurementRecord
from .offline_buffer import OfflineBuffer
from .robot import build_probe, build_robot
from .sensors.rs485_4in1 import build_sensor, resolve_sensor_mode


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


def _auth_headers() -> dict:
    """En-tête X-API-Key si AGRIBOTICS_API_KEY est configuré (sinon vide)."""
    key = os.getenv("AGRIBOTICS_API_KEY", "").strip()
    return {"X-API-Key": key} if key else {}


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


def _record_to_payload(record: MeasurementRecord) -> dict:
    """Construit le payload POST /api/measurements à partir d'un record."""
    return {
        "point": record.point,
        "humidity": record.humidity,
        "ph": record.ph,
        "temp": record.temp,
        "ec": record.ec,
        "quality": record.quality,
    }


def _post_payload(payload: dict) -> bool:
    """Poste un payload de mesure au backend. Renvoie True si accepté."""
    url = f"{_backend_url()}/api/measurements"
    try:
        r = requests.post(url, json=payload, timeout=5, headers=_auth_headers())
        if r.status_code >= 300:
            point = payload.get("point", "?")
            print(
                f"  [push] ⚠ échec HTTP {r.status_code} pour {point} : {r.text[:200]}",
                flush=True,
            )
            return False
        return True
    except requests.RequestException as err:
        print(f"  [push] ⚠ backend injoignable pour {payload.get('point', '?')} : {err}",
              flush=True)
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
    sensor_mode = resolve_sensor_mode()
    print(f"[mission] APP_MODE={mode} | SENSOR_MODE={sensor_mode} | "
          f"API={_backend_url()} | {len(points)} point(s)", flush=True)

    if reset:
        try:
            requests.post(f"{_backend_url()}/api/mission/reset", timeout=3, headers=_auth_headers())
            print("[mission] backend reset OK", flush=True)
        except requests.RequestException:
            print("[mission] backend non joignable — on continue en local", flush=True)

    robot = build_robot()
    # Le bras/sonde réutilise le PCA9685 déjà ouvert par le robot (même bus I2C).
    probe = build_probe(pca=getattr(robot, "_pca", None))
    sensor = build_sensor()
    # Le rythme d'acquisition suit APP_MODE (pas SENSOR_MODE) : sur le robot
    # réel, la collecte reste visible (~5 s) même quand les mesures sont mockées.
    manager = AcquisitionManager(sensor=sensor, interval_s=0.0 if mode == "mock" else 0.5)
    outbox = OfflineBuffer()
    records: List[MeasurementRecord] = []

    # Au démarrage : tenter de retransmettre les mesures laissées en file lors
    # d'une précédente coupure réseau (aucune mesure n'est perdue au champ).
    if outbox.pending():
        flushed = outbox.flush(_post_payload)
        print(f"[mission] outbox : {flushed} mesure(s) en attente retransmise(s), "
              f"{outbox.pending()} restante(s).", flush=True)

    aborted = False
    try:
        for p in points:
            if should_abort is not None and should_abort():
                print("[mission] ⛔ arrêt d'urgence demandé — mission interrompue.", flush=True)
                aborted = True
                break
            print(f"[mission] point {p.label}", flush=True)
            robot.move_to_point(p.x, p.y)        # déplacement réel/mock
            probe.lower_probe()                  # descente de la sonde
            probe.stabilize()                    # contact sol + stabilisation
            rec = manager.collect(p.label, x=p.x, y=p.y)  # lecture capteur
            probe.raise_probe()                  # remontée avant déplacement suivant
            if hasattr(robot, "point_complete"):
                robot.point_complete()           # bip + LEDs : mesure du point faite
            records.append(rec)
            payload = _record_to_payload(rec)
            if _post_payload(payload):
                tag = "✓ pushed"
            else:
                # Push raté → on persiste la mesure sur le disque du robot pour
                # la retransmettre plus tard. JAMAIS de perte de donnée.
                outbox.enqueue(payload)
                tag = "✎ bufferisé (outbox)"
            print(
                f"  [meas] H={rec.humidity}%  pH={rec.ph}  T={rec.temp}°C  "
                f"EC={rec.ec} mS/cm  quality={rec.quality}  {tag}",
                flush=True,
            )
        # Retour à l'origine en fin de mission (jamais après un arrêt d'urgence :
        # le robot doit rester immobile là où il a été stoppé).
        if not aborted and records and \
                os.getenv("ROBOT_RETURN_HOME", "0").strip().lower() in ("1", "true", "yes"):
            print("[mission] retour à l'origine (0, 0)", flush=True)
            robot.move_to_point(0.0, 0.0)
        if not aborted and records and hasattr(robot, "mission_complete"):
            robot.mission_complete()   # bip + clignotement de fin (robot réel)
    finally:
        # Dernière tentative de vidage de la file avant de rendre la main.
        if outbox.pending():
            outbox.flush(_post_payload)
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
            # Une erreur de mission (ex. obstacle persistant → RuntimeError) ne
            # doit JAMAIS tuer le daemon : le robot est déjà stoppé par le
            # finally de run_mission, on journalise et on retourne en attente.
            try:
                run_mission(
                    plan, reset=False,
                    should_abort=lambda: _fetch_command() in ("idle", "abort"),
                )
            except Exception as err:
                print(f"[watch] ⚠ mission interrompue : {err} — retour en attente",
                      flush=True)
            else:
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
