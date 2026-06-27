#!/usr/bin/env python3
"""
esp32_sensor_test.py — Test INDÉPENDANT de l'acquisition température + humidité
depuis l'ESP32 (DS18B20 + capteur capacitif) relié à la Pi en USB série.

L'ESP32 émet toutes les ~2 s :  « Température : 24.81 °C, Humidité : 53.16 % »

POINT CLÉ : on ouvre le port avec DTR/RTS au repos pour NE PAS réinitialiser
l'ESP32 à l'ouverture (sinon on ne capte que le boot ROM, illisible).

Usage :
    python3 esp32_sensor_test.py
    python3 esp32_sensor_test.py /dev/ttyUSB0
    python3 esp32_sensor_test.py /dev/serial/by-id/usb-Silicon_Labs_CP2102...-port0
    python3 esp32_sensor_test.py --once          # une seule trame puis quitte
"""
import sys
import time

import serial

# Réutilise le MÊME parseur que le code de production (source unique de vérité).
sys.path.insert(0, __file__.rsplit("/deploy/", 1)[0])
try:
    from raspberry_pi.sensors.esp32_sensor import parse_line
except Exception:                                   # repli si lancé hors repo
    import re
    _T = re.compile(r"emp[^:]*:\s*(-?\d+(?:[.,]\d+)?)", re.IGNORECASE)
    _H = re.compile(r"umid[^:]*:\s*(-?\d+(?:[.,]\d+)?)", re.IGNORECASE)

    def parse_line(line):
        mt, mh = _T.search(line), _H.search(line)
        return (float(mt.group(1).replace(",", ".")) if mt else None,
                float(mh.group(1).replace(",", ".")) if mh else None)


DEFAULT_PORT = "/dev/ttyUSB0"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    once = "--once" in sys.argv
    port = args[0] if args else DEFAULT_PORT

    print("=" * 56)
    print("  TEST ESP32 — température (DS18B20) + humidité (capacitif)")
    print(f"  port : {port}  @ 115200  (DTR/RTS au repos = pas de reset)")
    print("=" * 56)

    try:
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = 115200
        ser.timeout = 2.0
        ser.dtr = False
        ser.rts = False
        ser.open()
        ser.reset_input_buffer()
    except Exception as e:
        print(f"  ❌ Ouverture impossible : {e}")
        print("     → port correct ? (ls /dev/ttyUSB*)  occupé ? (sudo fuser le port)")
        sys.exit(1)

    n = 0
    t0 = time.time()
    try:
        while time.time() - t0 < 30:
            line = ser.readline().decode("utf-8", "replace")
            temp, hum = parse_line(line)
            if temp is None and hum is None:
                continue
            n += 1
            stamp = time.strftime("%H:%M:%S")
            ts = f"{temp:6.2f} °C" if temp is not None else "  --  "
            hs = f"{hum:6.2f} %" if hum is not None else "  --  "
            print(f"  [{stamp}] 🌡 {ts}    💧 {hs}")
            if once:
                break
    except KeyboardInterrupt:
        print("\n  🛑 Arrêt.")
    finally:
        ser.close()

    if n == 0:
        print("  ❌ Aucune trame valide reçue.")
        print("     → l'ESP32 émet-il bien à 115200 ? (Moniteur série Arduino)")
        print("     → fil TX de l'ESP32 OK ? cable USB data (pas charge seule) ?")
        sys.exit(1)
    print(f"  ✅ {n} trame(s) lue(s) — acquisition ESP32 fonctionnelle.")


if __name__ == "__main__":
    main()
