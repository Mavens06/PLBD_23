#!/usr/bin/env python3
"""
nema_test.py — Test NON-INTERACTIF du NEMA17 + A4988 piloté par les GPIO de la Pi.

Version non-interactive du sketch validé par Marius (STEP=GPIO26, DIR=GPIO27,
SLEEP/RESET au 3.3 V => driver toujours actif, pas de broche EN).

Usage :
    python3 nema_test.py                 # aller-retour court (2 s à 120 tr/min)
    python3 nema_test.py 5 120 H         # 5 s, 120 tr/min, sens H (descente)
    python3 nema_test.py 5 120 H --once  # un seul sens (pas de retour)

Sécurité : par défaut le moteur tourne dans un sens puis revient (même durée),
pour ne pas laisser le chariot en butée pendant la mise au point.
"""
import sys
import time

import RPi.GPIO as GPIO

STEP_PIN = 26          # phys. 37
DIR_PIN = 27           # phys. 13
STEPS_PER_REV = 200    # NEMA 17 (1.8°/pas)


START_RPM = 50          # vitesse de démarrage (sous le couple de décrochage)
ACCEL_S = 1.2           # durée des rampes d'accélération / décélération


def get_delay_from_rpm(rpm):
    if rpm <= 0:
        rpm = 1
    delay = 60.0 / (STEPS_PER_REV * rpm * 2)
    return max(delay, 0.00005)


def _rpm_at(elapsed, total, cruise):
    """Profil trapézoïdal : rampe START→cruise, plateau, puis cruise→START."""
    accel = min(ACCEL_S, total / 2.0)
    if accel <= 0:
        return cruise
    if elapsed < accel:                         # montée en vitesse
        return START_RPM + (cruise - START_RPM) * (elapsed / accel)
    if elapsed > total - accel:                 # ralentissement avant l'arrêt
        return START_RPM + (cruise - START_RPM) * ((total - elapsed) / accel)
    return cruise                               # plateau


def rotate(duration_sec, rpm, direction):
    GPIO.output(DIR_PIN, GPIO.HIGH if direction == 1 else GPIO.LOW)
    sens = "Haut/sens-1 (H)" if direction == 1 else "Bas/sens-0 (B)"
    print(f"  ▶ {duration_sec}s — cible {rpm} tr/min (rampe {START_RPM}→{rpm}) — {sens}")
    start = time.time()
    steps = 0
    while True:
        elapsed = time.time() - start
        if elapsed >= duration_sec:
            break
        delay = get_delay_from_rpm(_rpm_at(elapsed, duration_sec, rpm))
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(delay)
        steps += 1
    print(f"  ✅ {steps} pas effectués (avec rampe d'accél./décél.)")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    once = "--once" in sys.argv
    duration = float(args[0]) if len(args) > 0 else 2.0
    rpm = int(args[1]) if len(args) > 1 else 120
    direction = 0 if (len(args) > 2 and args[2].strip().upper() == "B") else 1

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(STEP_PIN, GPIO.OUT)
    GPIO.setup(DIR_PIN, GPIO.OUT)
    print("=" * 50)
    print("  TEST NEMA17 + A4988 (Pi GPIO 26/27) — non-interactif")
    print("=" * 50)
    try:
        rotate(duration, rpm, direction)
        if not once:
            time.sleep(0.5)
            print("  ↩ retour à la position de départ")
            rotate(duration, rpm, 0 if direction == 1 else 1)
    except KeyboardInterrupt:
        print("\n  🛑 Arrêt manuel")
    finally:
        GPIO.cleanup()
        print("  GPIO nettoyés. Fin.")


if __name__ == "__main__":
    main()
