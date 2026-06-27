#!/usr/bin/env python3
"""
ds18b20_test.py — Test INDÉPENDANT du capteur de température DS18B20 (1-Wire).

La DS18B20 est un capteur NUMÉRIQUE sur bus 1-Wire : la Raspberry Pi la lit
DIRECTEMENT (pas d'ESP32, pas d'ADC). Câblage du triplet (noir-rouge-jaune) :
    noir  = GND
    rouge = 3,3 V
    jaune = DATA  → relié au GPIO 1-Wire (défaut GPIO4, phys. pin 7)
Une résistance de tirage 4,7 kΩ entre DATA et 3,3 V est nécessaire (souvent déjà
présente sur les modules 3 broches).

PRÉ-REQUIS (une seule fois, puis reboot) — activer le bus 1-Wire :
    # Méthode simple :
    sudo raspi-config  →  Interface Options  →  1-Wire  →  Enable  →  reboot
    # OU à la main, ajouter dans /boot/firmware/config.txt (ou /boot/config.txt) :
    dtoverlay=w1-gpio                 # DATA sur GPIO4 (défaut)
    # si le fil jaune est sur un autre GPIO, ex. GPIO17 :
    dtoverlay=w1-gpio,gpiopin=17
    sudo reboot

Usage :
    python3 ds18b20_test.py            # lit en boucle toutes les 1 s (Ctrl-C pour stopper)
    python3 ds18b20_test.py --once     # une seule lecture puis quitte
    python3 ds18b20_test.py 0.5        # boucle toutes les 0,5 s
"""
import glob
import subprocess
import sys
import time

W1_DIR = "/sys/bus/w1/devices"


def _ensure_modules():
    """Charge les modules noyau 1-Wire s'ils ne le sont pas déjà (best effort)."""
    for mod in ("w1_gpio", "w1_therm"):
        try:
            subprocess.run(["modprobe", mod], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            pass  # pas de modprobe (rare) → on tente quand même la lecture


def find_sensors():
    """Retourne la liste des dossiers capteurs DS18B20 (préfixe 28-)."""
    return sorted(glob.glob(f"{W1_DIR}/28-*"))


def read_temp(sensor_dir):
    """Lit la température (°C) d'un capteur. None si lecture invalide (CRC KO)."""
    # Fichier moderne : 'temperature' = milli-°C, déjà validé par le driver.
    try:
        with open(f"{sensor_dir}/temperature") as f:
            raw = f.read().strip()
        if raw:
            return int(raw) / 1000.0
    except (OSError, ValueError):
        pass
    # Repli : ancien format 'w1_slave' (2 lignes, 'YES' = CRC ok, 't=' = milli-°C).
    try:
        with open(f"{sensor_dir}/w1_slave") as f:
            lines = f.read().splitlines()
        if len(lines) >= 2 and lines[0].strip().endswith("YES"):
            pos = lines[1].find("t=")
            if pos != -1:
                return int(lines[1][pos + 2:]) / 1000.0
    except (OSError, ValueError):
        pass
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    once = "--once" in sys.argv
    interval = float(args[0]) if args else 1.0

    print("=" * 52)
    print("  TEST DS18B20 (1-Wire) — lecture directe Raspberry Pi")
    print("=" * 52)

    _ensure_modules()
    time.sleep(0.3)

    sensors = find_sensors()
    if not sensors:
        print("  ❌ Aucun capteur 28-* trouvé dans", W1_DIR)
        print("     → Le bus 1-Wire est-il activé ? (raspi-config → 1-Wire, puis reboot)")
        print("     → Le fil JAUNE (DATA) est-il bien sur le GPIO du dtoverlay ?")
        print("     → Résistance de tirage 4,7 kΩ entre DATA et 3,3 V présente ?")
        print("     → Vérifie aussi :  ls", W1_DIR)
        sys.exit(1)

    print(f"  ✅ {len(sensors)} capteur(s) détecté(s) :")
    for s in sensors:
        print("     •", s.split('/')[-1])
    print("-" * 52)

    try:
        while True:
            stamp = time.strftime("%H:%M:%S")
            for s in sensors:
                temp = read_temp(s)
                sid = s.split('/')[-1]
                if temp is None:
                    print(f"  [{stamp}] {sid} : ⚠ lecture invalide (CRC)")
                else:
                    print(f"  [{stamp}] {sid} : 🌡  {temp:.2f} °C")
            if once:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n  🛑 Arrêt.")


if __name__ == "__main__":
    main()
