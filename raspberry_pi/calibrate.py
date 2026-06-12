"""
calibrate.py — Tests de calibration au sol, lançables à la main.

Chaque test lit la configuration courante dans .env (DRIVE_THROTTLE,
TURN_THROTTLE, marges gyro, …) : on édite .env, on relance le test, on
observe. Aucune modification de code nécessaire entre deux essais.

Usage (sur la Pi, robot AU SOL, IMMOBILE au lancement — calibration gyro) :

    # Ligne droite N secondes (calibrer ROBOT_SPEED_MPS = distance / durée)
    APP_MODE=hardware python3 -m raspberry_pi.calibrate --test drive --seconds 4

    # Virage 90° isolé (gyro si dispo) — vérifier l'angle et l'avance d'arc
    APP_MODE=hardware python3 -m raspberry_pi.calibrate --test turn-right
    APP_MODE=hardware python3 -m raspberry_pi.calibrate --test turn-left

    # Remise à l'état initial (moteurs zéro, direction centrée, bras home)
    APP_MODE=hardware python3 -m raspberry_pi.calibrate --test home

Procédure complète de calibration sur un nouveau sol :
  1) drive 4s   → mesurer la distance → ROBOT_SPEED_MPS = distance_m / 4
                  (si le robot cale : augmenter |DRIVE_THROTTLE|)
  2) turn-right / turn-left → si l'angle dépasse 90°, augmenter la marge du
     sens concerné (GYRO_STOP_MARGIN_*_DEG) ; s'il est en dessous, la réduire.
     Mesurer aussi l'AVANCE pendant le virage → TURN_ADVANCE_M.
  3) mission test : APP_MODE=hardware python3 -m raspberry_pi.main --plan plan_balayage.json
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from .robot import build_probe, build_robot  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibration au sol Agribotics")
    parser.add_argument("--test", required=True,
                        choices=["drive", "turn-right", "turn-left", "home"])
    parser.add_argument("--seconds", type=float, default=4.0,
                        help="Durée de la ligne droite (test drive). Défaut 4 s.")
    args = parser.parse_args()

    print("[calibrate] init (robot IMMOBILE — calibration gyro)…", flush=True)
    robot = build_robot()
    try:
        if args.test == "drive":
            print(f"[calibrate] ligne droite {args.seconds:.1f}s dans 3 s — "
                  "repère la position de départ…", flush=True)
            time.sleep(3)
            robot.forward(speed=100, duration=args.seconds)
            print(f"[calibrate] fini. ROBOT_SPEED_MPS = distance_mesurée_m / "
                  f"{args.seconds:.1f}", flush=True)

        elif args.test in ("turn-right", "turn-left"):
            target = "E" if args.test == "turn-right" else "W"
            print(f"[calibrate] virage {'droite' if target == 'E' else 'gauche'} "
                  "90° dans 3 s — repère l'orientation ET la position…", flush=True)
            time.sleep(3)
            if hasattr(robot, "_turn_to"):
                robot._turn_to(target)      # gyro si dispo, sinon chrono
            elif target == "E":
                robot.turn_right()
            else:
                robot.turn_left()
            print("[calibrate] fini. Vérifier : angle ≈ 90° ? avance pendant "
                  "le virage ≈ TURN_ADVANCE_M ?", flush=True)

        elif args.test == "home":
            probe = build_probe(pca=getattr(robot, "_pca", None))
            probe.close()                   # bras → posture home
            print("[calibrate] état initial : moteurs zéro, direction centrée, "
                  "bras home.", flush=True)
    finally:
        robot.stop()
        robot.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
