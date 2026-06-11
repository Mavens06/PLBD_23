"""
hardware_test.py — Test matériel simple et SÛR du PiCar-Pro.

À lancer directement sur la Raspberry Pi (APP_MODE=hardware) pour vérifier
moteurs et servo avant une mission. En mock (sur PC), il journalise la séquence
sans rien piloter — utile pour valider la logique.

Usage :
    APP_MODE=hardware python3 -m raspberry_pi.hardware_test --test motors
    APP_MODE=hardware python3 -m raspberry_pi.hardware_test --test servo
    APP_MODE=hardware python3 -m raspberry_pi.hardware_test --test all
    python3 -m raspberry_pi.hardware_test --test all        # mock (PC)

Sécurité (à lire avant le premier essai moteur) :
  • poser le robot sur un support (roues en l'air) ou le tenir ;
  • commencer à vitesse faible (option --speed, défaut 35) ;
  • garder une main près de l'interrupteur ;
  • Ctrl-C → arrêt immédiat (le robot est stoppé proprement).
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

# Même .env que le backend / l'orchestrateur (cf. main.py) : le test matériel
# doit voir PROBE_SERVO_CHANNEL, STEER_*_DEG, DRIVE_THROTTLE_SCALE…
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from .robot import build_probe, build_robot


def test_motors(speed: int, dur: float) -> None:
    print(f"[test] MOTEURS (speed={speed}, {dur}s/segment) — robot sur support !", flush=True)
    robot = build_robot()
    try:
        robot.forward(speed=speed, duration=dur)
        robot.stop()
        robot.backward(speed=speed, duration=dur)
        robot.stop()
        robot.turn_left(speed=speed, duration=dur)
        robot.turn_right(speed=speed, duration=dur)
        robot.stop()
        print("[test] moteurs : OK", flush=True)
    finally:
        robot.stop()
        robot.close()


def test_servo() -> None:
    print("[test] SERVO / SONDE — descente, stabilisation, remontée", flush=True)
    probe = build_probe()
    try:
        probe.lower_probe()
        probe.stabilize(2.0)
        probe.raise_probe()
        print("[test] servo/sonde : OK", flush=True)
    finally:
        probe.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Test matériel PiCar-Pro (sûr).")
    parser.add_argument("--test", choices=["motors", "servo", "all"], default="all",
                        help="Quoi tester (défaut : all).")
    parser.add_argument("--speed", type=int, default=35,
                        help="Vitesse moteurs 0-100 (défaut 35, faible = sûr).")
    parser.add_argument("--duration", type=float, default=1.0,
                        help="Durée de chaque segment moteur en secondes (défaut 1.0).")
    args = parser.parse_args()

    mode = os.getenv("APP_MODE", "mock").lower()
    print(f"[test] APP_MODE={mode}", flush=True)

    try:
        if args.test in ("motors", "all"):
            test_motors(args.speed, args.duration)
        if args.test in ("servo", "all"):
            test_servo()
    except KeyboardInterrupt:
        print("\n[test] interruption — arrêt.", flush=True)
        try:
            build_robot().stop()
        except Exception:
            pass
        return 130
    print("[test] terminé.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
