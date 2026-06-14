"""
adeept_controller.py — Pilotage RÉEL du robot Adeept PiCar-Pro.

Calqué sur le code VALIDÉ sur le robot de l'équipe (Code_PLBD_23_mission.py) :
  • PCA9685 (adafruit_pca9685) à l'adresse 0x5f, 50 Hz.
  • 2 moteurs DC (adafruit_motor.motor.DCMotor) :
        moteur G = canaux PCA (15, 14)
        moteur D = canaux PCA (12, 13)
  • 1 servo de DIRECTION sur le canal 0 :
        centre = 85°, gauche = 0° (à fond), droite = 180° (à fond).
  • Sens des moteurs validé : la marche AVANT correspond à un throttle
    NÉGATIF (DRIVE_THROTTLE = -0.15) ; les virages utilisent un throttle
    POSITIF (TURN_THROTTLE = 0.18). Ces signes sont ceux du code testé —
    ne pas les « corriger » sans réessayer sur le robot.

Architecture « voiture » (2 moteurs de propulsion + 1 servo de braquage) :
les virages se font en ARC DE CERCLE — braquage à fond + avance pendant
TURN_90_S (≈1.2 s pour 90°, 2× pour un demi-tour), comme validé.

Navigation : MANHATTAN par cap (N/E/S/W) — pour rejoindre (x, y), le robot
s'oriente puis parcourt |dx| puis |dy| en lignes droites temporisées
(dead-reckoning, pas d'encodeurs). `manhattan_legs()` est la partie pure
(testable sans matériel).

ÉCHELLE MONDE (`ROBOT_WORLD_SCALE`) : le plan de mission de l'interface est en
mètres « terrain » ; le robot multiplie chaque distance par ce facteur pour
rejouer la mission sur une surface réduite (démo 1 m × 1 m : la grille 3×3 par
défaut s'étend sur 6 m → scale 0.15 ≈ 90 cm). L'interface, le backend et les
mesures ne voient JAMAIS cette échelle — uniquement le déplacement physique.

Toutes les valeurs sont surchargeables par variables d'environnement (cf.
.env.example). Les imports matériels (busio, adafruit_*) sont PARESSEUX pour
que ce module reste importable sur un PC de dev sans GPIO.
"""

from __future__ import annotations

import os
import time
from typing import List, Tuple

from .base import ProbeController, RobotController
from .signals import MissionSignals


HEADINGS = ["N", "E", "S", "W"]


def _log(msg: str) -> None:
    print(f"  [robot:adeept] {msg}", flush=True)


def _envf(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


def _envi(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


def manhattan_legs(
    x0: float, y0: float, x1: float, y1: float, heading: str,
) -> Tuple[List[Tuple[str, object]], str]:
    """
    Décompose le trajet (x0,y0)→(x1,y1) en segments Manhattan.

    Renvoie ([("turn", cap), ("drive", distance_m), …], cap_final).
    Axe X = Est/Ouest, axe Y = Nord/Sud (dy > 0 → "N", comme le code validé).
    L'axe ALIGNÉ AVEC LE CAP COURANT est traité en premier : le robot
    prolonge sa trajectoire avant de tourner (cap N/S → Y d'abord, cap E/W →
    X d'abord). Validé au sol — c'est le mouvement « naturel » attendu.
    Fonction PURE : aucune dépendance matérielle, testée dans tests/.
    """
    legs: List[Tuple[str, object]] = []
    h = heading if heading in HEADINGS else "N"
    dx, dy = x1 - x0, y1 - y0
    x_axis = (dx, "E", "W")
    y_axis = (dy, "N", "S")
    axes = (x_axis, y_axis) if h in ("E", "W") else (y_axis, x_axis)
    for delta, pos_cap, neg_cap in axes:
        if abs(delta) < 1e-6:
            continue
        cap = pos_cap if delta > 0 else neg_cap
        if cap != h:
            legs.append(("turn", cap))
            h = cap
        legs.append(("drive", abs(delta)))
    return legs, h


class AdeeptRobotController(RobotController):
    """Pilote réel des moteurs + servo de direction du PiCar-Pro."""

    def __init__(self) -> None:
        # Imports matériels paresseux : ne s'exécutent que sur la Pi.
        import board
        import busio
        from adafruit_pca9685 import PCA9685
        from adafruit_motor import motor as _motor

        self._motor_lib = _motor

        # --- Configuration (défauts = valeurs VALIDÉES sur le robot) --------
        self._addr = int(os.getenv("PCA9685_ADDRESS", "0x5f"), 0)
        self._freq = _envi("PCA9685_FREQUENCY", 50)
        m1a, m1b = _envi("MOTOR_LEFT_IN1", 15), _envi("MOTOR_LEFT_IN2", 14)
        m2a, m2b = _envi("MOTOR_RIGHT_IN1", 12), _envi("MOTOR_RIGHT_IN2", 13)
        self._steer_ch = _envi("STEER_SERVO_CHANNEL", 0)
        self._steer_center = _envf("STEER_CENTER_DEG", 85)
        self._steer_left = _envf("STEER_LEFT_DEG", 0)
        self._steer_right = _envf("STEER_RIGHT_DEG", 180)
        # Throttles SIGNÉS issus du code validé : avant = -0.15, virage = +0.18.
        self._drive_throttle = _envf("DRIVE_THROTTLE", -0.15)
        self._turn_throttle = _envf("TURN_THROTTLE", 0.18)
        self._turn_90_s = _envf("TURN_90_S", 1.2)
        # Après le virage : roues recentrées + courte avance pour réaligner
        # le châssis avant la prochaine ligne droite (validé au sol).
        self._straighten_s = _envf("TURN_STRAIGHTEN_S", 0.4)
        # Le virage en arc AVANCE le robot (~20 cm mesurés au sol) : cette
        # distance est déduite de la ligne droite qui suit chaque rotation,
        # sinon l'erreur s'accumule à chaque virage du parcours.
        self._turn_advance_m = _envf("TURN_ADVANCE_M", 0.0)
        # Pause d'arrêt complet en fin de virage (stabilisation du châssis).
        self._turn_pause_s = _envf("TURN_PAUSE_S", 1.0)
        # ~35-40 cm en 2.0 s à 0.15 de throttle → ≈ 0.19 m/s.
        self._speed_mps = _envf("ROBOT_SPEED_MPS", 0.19)
        # Échelle plan→physique (démo sur surface réduite). 1.0 = grandeur réelle.
        self._world_scale = max(0.01, _envf("ROBOT_WORLD_SCALE", 1.0))

        # --- Arrêt net & alignement (corrections de déplacement) -------------
        # Les moteurs DC tournent en ROUE LIBRE à throttle=0 : à l'arrivée sur
        # un point le robot « glisse » encore un peu — et la sonde descendait
        # pendant ce glissement. FREIN ACTIF (brève impulsion inverse) en fin de
        # ligne droite + pause d'immobilisation avant de rendre la main.
        self._brake_pulse_s = _envf("BRAKE_PULSE_S", 0.08)
        self._settle_pause_s = _envf("SETTLE_PAUSE_S", 0.6)
        # Trim du servo de direction : compense un désalignement MÉCANIQUE des
        # roues (le robot « penche » en ligne droite). Signe à régler au sol :
        # si le robot dérive vers la GAUCHE, augmenter (ex. +4) ; vers la DROITE,
        # diminuer (ex. -4). N'affecte que les lignes droites.
        self._steer_trim = _envf("STEER_TRIM_DEG", 0.0)
        # Maintien de cap au gyroscope pendant les lignes droites (annule la
        # dérive résiduelle que le trim seul ne corrige pas). Opt-in : si la
        # correction AGGRAVE la dérive, le signe est inversé sur ce châssis →
        # mettre HEADING_HOLD_SIGN=-1.
        self._heading_hold = os.getenv("HEADING_HOLD", "0").strip().lower() \
            in ("1", "true", "yes")
        self._heading_kp = _envf("HEADING_HOLD_KP", 2.0)
        self._heading_sign = 1.0 if _envf("HEADING_HOLD_SIGN", 1.0) >= 0 else -1.0
        self._heading_max_corr = _envf("HEADING_HOLD_MAX_DEG", 25.0)
        self._heading_debug = os.getenv("HEADING_DEBUG", "0").strip().lower() \
            in ("1", "true", "yes")
        # Manœuvre en 3 points (TURN_MODE=kturn) : durée d'une impulsion
        # avant/arrière braquée. Plus court = empreinte plus petite, plus de
        # va-et-vient ; plus long = rotation plus rapide, empreinte plus large.
        self._kturn_pulse_s = _envf("KTURN_PULSE_S", 0.5)
        # Throttle (magnitude) des impulsions du k-turn — séparé de la ligne
        # droite : celle-ci tourne lentement pour la précision (DRIVE_THROTTLE
        # bas), mais le k-turn doit rouler franchement pour ne pas caler.
        self._kturn_throttle = abs(_envf("KTURN_THROTTLE", 0.15))
        # Recul de compensation APRÈS un virage en ARC (gyro) : l'arc fait
        # avancer le robot ; on recule de cette distance pour revenir sur le
        # point. Préféré à la déduction sur la ligne droite suivante (qui échoue
        # quand la ligne est courte ou orientée autrement). À calibrer au sol.
        self._turn_backup_m = _envf("TURN_BACKUP_M", 0.0)

        # --- Initialisation matérielle --------------------------------------
        i2c = busio.I2C(board.SCL, board.SDA)
        self._pca = PCA9685(i2c, address=self._addr)
        self._pca.frequency = self._freq
        self._left = _motor.DCMotor(self._pca.channels[m1a], self._pca.channels[m1b])
        self._right = _motor.DCMotor(self._pca.channels[m2a], self._pca.channels[m2b])

        self._x = 0.0
        self._y = 0.0
        self._heading = "N"
        self._set_angle(self._steer_ch, self._steer_center)

        # --- LEDs / buzzer (no-op si indisponibles) --------------------------
        self._signals = MissionSignals()

        # --- Ultrason anti-obstacle (broches validées : trigger 23, écho 24) -
        self._obstacle_cm = _envf("OBSTACLE_MIN_DISTANCE_CM", 12.0)
        self._obstacle_timeout_s = _envf("OBSTACLE_TIMEOUT_S", 20.0)
        self._distance_sensor = None
        if os.getenv("OBSTACLE_AVOIDANCE", "1").strip().lower() in ("1", "true", "yes"):
            try:
                from gpiozero import DistanceSensor
                self._distance_sensor = DistanceSensor(
                    echo=_envi("ULTRASONIC_ECHO_PIN", 24),
                    trigger=_envi("ULTRASONIC_TRIGGER_PIN", 23),
                    max_distance=2,
                )
            except Exception as err:
                _log(f"⚠ ultrason indisponible ({err}) — anti-obstacle désactivé.")

        # --- Gyroscope MPU6500 (rotations asservies) -------------------------
        # TURN_MODE=kturn : MANŒUVRE EN 3 POINTS (avant braqué ↔ arrière contre-
        # braqué) — rotation quasi sur place SANS raclage, recommandée au sol ·
        # TURN_MODE=pivot : rotation sur place (moteurs G/D opposés, peut racler
        # les roues) · TURN_MODE=arc : virage en arc (avance d'arc géométrique).
        # Avec gyro : on tourne jusqu'à l'angle MESURÉ (90°/180°), indépendant
        # des batteries et du sol. Sans gyro : repli arc chronométré.
        self._turn_mode = os.getenv("TURN_MODE", "arc").strip().lower()
        self._pivot_throttle = abs(_envf("PIVOT_THROTTLE", 0.15))
        self._pivot_invert = os.getenv("PIVOT_INVERT", "0").strip().lower() \
            in ("1", "true", "yes")
        # Marge d'arrêt anticipé (inertie) — séparée par sens car la friction
        # n'est pas symétrique sur ce châssis (validé au sol).
        default_margin = _envf("GYRO_STOP_MARGIN_DEG", 8.0)
        self._gyro_margin_right = _envf("GYRO_STOP_MARGIN_RIGHT_DEG", default_margin)
        self._gyro_margin_left = _envf("GYRO_STOP_MARGIN_LEFT_DEG", default_margin)
        self._turn_timeout_s = _envf("TURN_TIMEOUT_S", 10.0)
        self._gyro = None
        if os.getenv("GYRO_ENABLED", "1").strip().lower() in ("1", "true", "yes"):
            try:
                from .imu import GyroZ
                self._gyro = GyroZ()   # calibration : le robot doit être immobile
            except Exception as err:
                _log(f"⚠ gyroscope indisponible ({err}) — rotations chronométrées.")

        _log(f"prêt (PCA 0x{self._addr:02x} @ {self._freq}Hz, "
             f"drive={self._drive_throttle}, turn={self._turn_throttle}, "
             f"scale={self._world_scale}, "
             f"ultrason={'on' if self._distance_sensor else 'off'}, "
             f"rotation={self._turn_mode}"
             f"{'+gyro' if self._gyro else ' chronométrée'}, "
             f"trim={self._steer_trim:+.0f}°, "
             f"cap={'hold' if self._heading_hold and self._gyro else 'libre'})")

    # -- Bas niveau ----------------------------------------------------------
    def _set_angle(self, channel: int, angle: float) -> None:
        """Positionne un servo (miroir exact du set_angle validé)."""
        from adafruit_motor import servo
        s = servo.Servo(self._pca.channels[channel], min_pulse=500, max_pulse=2400,
                        actuation_range=180)
        s.angle = max(0.0, min(180.0, float(angle)))

    def _throttle(self, value: float) -> None:
        value = max(-1.0, min(1.0, value))
        self._left.throttle = value
        self._right.throttle = value

    def _throttle_lr(self, left: float, right: float) -> None:
        """Commande différentielle (pivot sur place)."""
        self._left.throttle = max(-1.0, min(1.0, left))
        self._right.throttle = max(-1.0, min(1.0, right))

    def _read_distance_cm(self) -> float | None:
        if self._distance_sensor is None:
            return None
        try:
            return float(self._distance_sensor.distance * 100.0)
        except Exception:
            return None

    def _ensure_path_clear(self) -> None:
        """
        Vérifie l'ultrason. Si un obstacle est plus près que le seuil :
        arrêt immédiat + LED + bip, puis ATTENTE que la voie se libère
        (démo : une main retirée → la mission reprend toute seule).
        Au-delà de OBSTACLE_TIMEOUT_S, RuntimeError → la mission s'interrompt
        proprement (le finally de run_mission stoppe le robot).
        """
        d = self._read_distance_cm()
        if d is None or d >= self._obstacle_cm:
            return
        self._throttle(0.0)
        self._signals.alert_on()
        self._signals.beep("C4", 0.2)
        _log(f"⛔ obstacle à {d:.1f} cm — arrêt, attente de dégagement "
             f"(max {self._obstacle_timeout_s:.0f}s)")
        deadline = time.monotonic() + self._obstacle_timeout_s
        while True:
            time.sleep(0.3)
            d = self._read_distance_cm()
            if d is None or d >= self._obstacle_cm:
                break
            if time.monotonic() > deadline:
                self._signals.alert_off()
                raise RuntimeError(f"obstacle persistant à {d:.1f} cm")
        self._signals.alert_off()
        _log("voie dégagée — reprise du déplacement")

    def _drive_straight(self, throttle: float, duration: float,
                        check_obstacles: bool = True,
                        correct_heading: bool = True) -> None:
        """
        Ligne droite temporisée puis FREIN ACTIF (anti-glissement) en fin de
        segment : le robot s'immobilise net au lieu de rouler en roue libre.

        Deux corrections de trajectoire :
          • trim statique du servo (STEER_TRIM_DEG) — désalignement mécanique ;
          • maintien de cap au gyroscope (HEADING_HOLD) — on intègre la dérive
            de lacet et on contre-braque proportionnellement.
        L'ultrason est vérifié toutes les ~0.4 s pendant le déplacement
        (l'obstacle peut surgir en cours de segment, pas seulement avant).
        """
        center = self._steer_center + self._steer_trim
        self._set_angle(self._steer_ch, center)
        hold = self._heading_hold and self._gyro is not None and correct_heading
        remaining = max(0.0, duration)
        heading_dev = 0.0                       # dérive de cap intégrée (°)
        since_obstacle = 0.0
        since_debug = 0.0
        last = time.monotonic()
        self._throttle(throttle)
        while remaining > 0:
            dt = min(0.05 if hold else 0.4, remaining)
            time.sleep(dt)
            remaining -= dt
            now = time.monotonic()
            if hold:
                rate = self._gyro.rate_dps()
                heading_dev += rate * (now - last)
                corr = self._heading_sign * self._heading_kp * heading_dev
                corr = max(-self._heading_max_corr, min(self._heading_max_corr, corr))
                self._set_angle(self._steer_ch, center - corr)
                since_debug += (now - last)
                if self._heading_debug and since_debug >= 0.3:
                    since_debug = 0.0
                    _log(f"cap: taux={rate:+.1f}°/s dev={heading_dev:+.1f}° "
                         f"corr={corr:+.1f}° → braquage={center - corr:.0f}°")
            last = now
            since_obstacle += dt
            if check_obstacles and since_obstacle >= 0.4:
                since_obstacle = 0.0
                self._ensure_path_clear()       # peut suspendre puis reprendre
                self._throttle(throttle)        # relance après une pause éventuelle
                last = time.monotonic()         # évite un saut d'intégration
        # Frein actif : brève impulsion en sens inverse pour tuer l'inertie,
        # puis arrêt franc. Sans ça le robot « glisse » sur le point de mesure.
        if self._brake_pulse_s > 0:
            self._throttle(-throttle * 0.6)
            time.sleep(self._brake_pulse_s)
        self._throttle(0.0)

    def _reverse_distance(self, dist_m: float) -> None:
        """Recule en ligne droite d'une distance donnée (sans maintien de cap :
        la géométrie de braquage s'inverse en marche arrière). Sert à annuler
        l'avance provoquée par un virage en arc."""
        if dist_m <= 0 or self._speed_mps <= 0:
            return
        duration = dist_m / self._speed_mps
        _log(f"recul compensation d'arc : {dist_m:.2f} m ≈ {duration:.1f}s")
        # avant = drive_throttle (négatif) → arrière = -drive_throttle (positif)
        self._drive_straight(-self._drive_throttle, duration,
                             check_obstacles=False, correct_heading=False)

    def _turn_arc(self, steer_deg: float, duration: float) -> None:
        """Virage en arc validé : braquage à fond + avance, puis recentrage
        et courte avance roues droites pour redresser le châssis."""
        self._set_angle(self._steer_ch, steer_deg)
        time.sleep(0.1)
        self._throttle(self._turn_throttle)
        time.sleep(max(0.0, duration))
        self._throttle(0.0)
        self._set_angle(self._steer_ch, self._steer_center)
        # Pause d'arrêt complet après le virage : le châssis se stabilise
        # avant la ligne droite suivante (précision du reliquat compensé).
        if self._turn_pause_s > 0:
            time.sleep(self._turn_pause_s)
        if self._straighten_s > 0:
            time.sleep(0.1)
            self._throttle(self._drive_throttle)
            time.sleep(self._straighten_s)
            self._throttle(0.0)

    def _gyro_drive_pulse(self, throttle: float, steer_deg: float,
                          max_s: float) -> float:
        """Avance/recule braqué pendant `max_s` en intégrant |gyro|.
        Renvoie l'angle (°) balayé par le châssis pendant l'impulsion."""
        self._set_angle(self._steer_ch, steer_deg)
        time.sleep(0.05)
        swept = 0.0
        last = time.monotonic()
        end = last + max(0.0, max_s)
        self._throttle(throttle)
        while time.monotonic() < end:
            time.sleep(0.005)
            now = time.monotonic()
            swept += abs(self._gyro.rate_dps()) * (now - last)
            last = now
        self._throttle(0.0)
        return swept

    def _turn_kturn(self, target_deg: float, clockwise: bool) -> None:
        """
        Rotation quasi SUR PLACE par MANŒUVRE EN 3 POINTS (demi-tours de volant
        alternés), asservie au gyroscope.

        Sur une voiture (direction Ackermann à l'avant), une « rotation sur
        place » par moteurs opposés fait RACLER les roues. Ici on alterne :
          1) AVANT, roues braquées vers le sens du virage  → tourne le châssis ;
          2) ARRIÈRE, roues contre-braquées               → tourne ENCORE dans
             le MÊME sens, et annule la translation de l'étape 1.
        Résultat : empreinte minimale (≈ sur place), roulement propre. On répète
        jusqu'à l'angle MESURÉ (moins la marge d'inertie). Garde-fou : timeout.
        """
        fwd_steer = self._steer_right if clockwise else self._steer_left
        bwd_steer = self._steer_left if clockwise else self._steer_right
        margin = self._gyro_margin_right if clockwise else self._gyro_margin_left
        pulse = self._kturn_pulse_s
        # Avant = throttle NÉGATIF sur ce câblage ; arrière = positif.
        fwd_t = -self._kturn_throttle
        bwd_t = self._kturn_throttle
        angle = 0.0
        deadline = time.monotonic() + self._turn_timeout_s
        try:
            while angle < target_deg - margin and time.monotonic() < deadline:
                # 1) avance braqué dans le sens du virage
                angle += self._gyro_drive_pulse(fwd_t, fwd_steer, pulse)
                if angle >= target_deg - margin:
                    break
                time.sleep(0.12)
                # 2) recule contre-braqué (même sens de rotation, translation annulée)
                angle += self._gyro_drive_pulse(bwd_t, bwd_steer, pulse)
                time.sleep(0.12)
        finally:
            self._throttle(0.0)
            try:
                self._set_angle(self._steer_ch, self._steer_center + self._steer_trim)
            except Exception:
                pass
        _log(f"rotation k-turn : {angle:.0f}° mesurés (cible {target_deg}°)")
        if self._turn_pause_s > 0:
            time.sleep(self._turn_pause_s)

    def _turn_gyro(self, target_deg: float, clockwise: bool) -> None:
        """
        Rotation ASSERVIE AU GYROSCOPE : on met le robot en rotation (pivot
        différentiel ou arc selon TURN_MODE) et on intègre la vitesse angulaire
        jusqu'à l'angle cible (moins GYRO_STOP_MARGIN_DEG pour l'inertie).
        Garde-fou : timeout TURN_TIMEOUT_S → arrêt propre.
        """
        # Mise en rotation
        if self._turn_mode == "pivot":
            # Roues avant braquées DANS le sens du pivot : elles roulent le
            # long du cercle de rotation au lieu de racler latéralement.
            self._set_angle(self._steer_ch,
                            self._steer_right if clockwise else self._steer_left)
            time.sleep(0.1)
            t = self._pivot_throttle * (-1.0 if self._pivot_invert else 1.0)
            # avant = throttle négatif sur ce câblage → pivot horaire (droite)
            # = roue gauche en avant (-t), roue droite en arrière (+t)
            if clockwise:
                self._throttle_lr(-t, t)
            else:
                self._throttle_lr(t, -t)
        else:
            self._set_angle(self._steer_ch,
                            self._steer_right if clockwise else self._steer_left)
            time.sleep(0.1)
            self._throttle(self._turn_throttle)

        margin = self._gyro_margin_right if clockwise else self._gyro_margin_left
        angle = 0.0
        last = time.monotonic()
        deadline = last + self._turn_timeout_s
        try:
            while True:
                now = time.monotonic()
                angle += abs(self._gyro.rate_dps()) * (now - last)
                last = now
                if angle >= target_deg - margin:
                    break
                if now > deadline:
                    _log(f"⚠ rotation gyro : timeout à {angle:.0f}° "
                         f"(cible {target_deg}°)")
                    break
                time.sleep(0.004)
        finally:
            self._throttle_lr(0.0, 0.0)
            try:
                self._set_angle(self._steer_ch, self._steer_center)
            except Exception:
                pass
        _log(f"rotation gyro : {angle:.0f}° mesurés (cible {target_deg}°, "
             f"mode {self._turn_mode})")
        if self._turn_pause_s > 0:
            time.sleep(self._turn_pause_s)
        # Virage en ARC : il a fait AVANCER le robot → on recule de la distance
        # provoquée par l'arc pour revenir sur le point (compensation directe).
        if self._turn_mode != "pivot" and self._turn_backup_m > 0:
            self._reverse_distance(self._turn_backup_m)
            if self._turn_pause_s > 0:
                time.sleep(self._turn_pause_s)

    def _turn_to(self, target: str) -> None:
        """Oriente le robot vers le cap cible (gyro si dispo, sinon chrono)."""
        delta = (HEADINGS.index(target) - HEADINGS.index(self._heading)) % 4
        if delta == 0:
            return
        name = {1: "rotation droite", 2: "demi-tour", 3: "rotation gauche"}[delta]
        _log(f"{name} → {target}")
        if self._gyro is not None:
            clockwise = delta in (1, 2)
            target = 180.0 if delta == 2 else 90.0
            if self._turn_mode == "kturn":
                self._turn_kturn(target, clockwise)
            else:
                self._turn_gyro(target, clockwise)
        elif delta == 1:
            self._turn_arc(self._steer_right, self._turn_90_s)
        elif delta == 2:
            self._turn_arc(self._steer_right, self._turn_90_s * 2)
        else:
            self._turn_arc(self._steer_left, self._turn_90_s)
        self._heading = target

    # -- Interface RobotController ------------------------------------------
    def forward(self, speed: int = 50, duration: float = 1.0) -> None:
        _log(f"avance (speed={speed}, {duration:.1f}s)")
        self._drive_straight(self._drive_throttle * max(0, min(100, speed)) / 100.0,
                             duration)

    def backward(self, speed: int = 50, duration: float = 1.0) -> None:
        _log(f"recule (speed={speed}, {duration:.1f}s)")
        # Pas de vérification d'obstacle : l'ultrason regarde vers l'avant.
        self._drive_straight(-self._drive_throttle * max(0, min(100, speed)) / 100.0,
                             duration, check_obstacles=False)

    def turn_left(self, speed: int = 40, duration: float = 1.0) -> None:
        _log(f"tourne à gauche ({duration:.1f}s)")
        self._turn_arc(self._steer_left, duration)

    def turn_right(self, speed: int = 40, duration: float = 1.0) -> None:
        _log(f"tourne à droite ({duration:.1f}s)")
        self._turn_arc(self._steer_right, duration)

    def stop(self) -> None:
        # Arrêt d'urgence : doit rester fiable même si un servo échoue.
        try:
            self._throttle(0.0)
        finally:
            try:
                self._set_angle(self._steer_ch, self._steer_center)
            except Exception:
                pass
        _log("STOP")

    def move_to_point(self, x: float, y: float) -> None:
        legs, final_heading = manhattan_legs(self._x, self._y, x, y, self._heading)
        if not legs:
            _log(f"déjà au point (x={x}, y={y})")
            return
        _log(f"va au point (x={x}, y={y}) depuis ({self._x}, {self._y}) "
             f"cap {self._heading} — échelle {self._world_scale}")
        # Avance d'arc à déduire de la ligne droite suivante UNIQUEMENT si elle
        # n'est pas déjà compensée autrement :
        #  • rotation sur place (pivot / k-turn au gyro) → pas d'avance ;
        #  • virage en arc avec recul de compensation (TURN_BACKUP_M) → déjà annulée.
        in_place_turn = self._gyro is not None and self._turn_mode in ("pivot", "kturn")
        arc_backup = self._turn_mode != "pivot" and self._turn_backup_m > 0
        arc_advance = 0.0 if (in_place_turn or arc_backup) else self._turn_advance_m
        pending_arc_advance = 0.0
        for kind, value in legs:
            if kind == "turn":
                self._turn_to(str(value))
                pending_arc_advance = arc_advance
            else:
                dist_plan = float(value)
                dist_phys = dist_plan * self._world_scale
                if pending_arc_advance > 0:
                    comp = min(pending_arc_advance, dist_phys)
                    dist_phys -= comp
                    pending_arc_advance = 0.0
                    _log(f"compensation virage : -{comp:.2f} m (l'arc a déjà avancé)")
                duration = dist_phys / self._speed_mps if self._speed_mps > 0 else 0.0
                _log(f"ligne droite {dist_plan:.2f} m plan → {dist_phys:.2f} m réel "
                     f"≈ {duration:.1f}s")
                if duration > 0:
                    self._drive_straight(self._drive_throttle, duration)
                time.sleep(0.2)
        self._x, self._y = x, y
        self._heading = final_heading
        self.stop()
        # Immobilisation COMPLÈTE avant de rendre la main : la sonde ne doit
        # JAMAIS descendre pendant que le robot glisse encore (cf. frein actif).
        if self._settle_pause_s > 0:
            time.sleep(self._settle_pause_s)
        self._signals.blink(0.2)   # point atteint (validé : blink à l'arrivée)

    def mission_start(self) -> None:
        """Signal de début de mission : buzzer 4 s + LEDs clignotantes 4 s."""
        _log("signal de début de mission (4s)")
        self._signals.signal(buzzer_s=4.0, blink_s=4.0)

    def point_complete(self) -> None:
        """Signal après CHAQUE mesure : buzzer 1 s + LEDs clignotantes 2 s."""
        self._signals.signal(buzzer_s=1.0, blink_s=2.0)

    def mission_complete(self) -> None:
        """Signal de fin de mission : identique au départ (buzzer 4 s + LEDs 4 s)."""
        _log("signal de fin de mission (4s)")
        self._signals.signal(buzzer_s=4.0, blink_s=4.0)

    def close(self) -> None:
        try:
            self.stop()
        finally:
            try:
                if self._distance_sensor is not None:
                    self._distance_sensor.close()
            except Exception:
                pass
            if self._gyro is not None:
                self._gyro.close()
            self._signals.close()
            try:
                self._pca.deinit()
            except Exception:
                pass


class AdeeptProbeController(ProbeController):
    """
    Bras du PiCar-Pro utilisé comme SONDE (séquence validée sur le robot).

    4 servos : épaule = PROBE_SERVO_CHANNEL (défaut 2, c'est lui qui descend),
    les autres tenus en posture « home » (PROBE_ARM_HOME, défaut 1:90,3:140,4:80).
      • position haute  : épaule à PROBE_ANGLE_UP (90°)
      • descente sonde  : épaule à PROBE_ANGLE_DOWN (150°)
    Activée seulement si `PROBE_SERVO_CHANNEL` est défini (cf. __init__.py).
    Réutilise le même PCA9685 que le robot si fourni, sinon en ouvre un.
    """

    def __init__(self, channel: int, up_deg: float, down_deg: float,
                 stabilize_s: float, pca=None,
                 home_pose: List[Tuple[int, float]] | None = None) -> None:
        self._channel = channel
        self._up = up_deg
        self._down = down_deg
        self._stab = stabilize_s
        self._home_pose = home_pose if home_pose is not None else \
            [(1, 90.0), (3, 140.0), (4, 80.0)]
        if pca is None:
            import board
            import busio
            from adafruit_pca9685 import PCA9685
            i2c = busio.I2C(board.SCL, board.SDA)
            pca = PCA9685(i2c, address=int(os.getenv("PCA9685_ADDRESS", "0x5f"), 0))
            pca.frequency = _envi("PCA9685_FREQUENCY", 50)
        self._pca = pca
        self.arm_home()

    def _set_angle(self, channel: int, angle: float) -> None:
        from adafruit_motor import servo
        s = servo.Servo(self._pca.channels[channel], min_pulse=500,
                        max_pulse=2400, actuation_range=180)
        s.angle = max(0.0, min(180.0, float(angle)))

    def _pose(self, shoulder_deg: float, shoulder_sleep: float) -> None:
        """Applique la posture complète, servos dans l'ordre des canaux."""
        full = sorted(self._home_pose + [(self._channel, shoulder_deg)])
        for ch, deg in full:
            self._set_angle(ch, deg)
            time.sleep(shoulder_sleep if ch == self._channel else 0.4)

    def arm_home(self) -> None:
        _log("bras : posture home")
        self._pose(self._up, 0.5)

    def lower_probe(self) -> None:
        _log(f"sonde : descente (épaule servo {self._channel} → {self._down}°)")
        self._pose(self._down, 0.8)
        _log("sonde : en position de mesure")

    def stabilize(self, seconds: float = None) -> None:  # type: ignore[assignment]
        s = self._stab if seconds is None else seconds
        _log(f"sonde : stabilisation {s:.1f}s")
        time.sleep(max(0.0, s))

    def raise_probe(self) -> None:
        _log(f"sonde : remontée (épaule servo {self._channel} → {self._up}°)")
        self._set_angle(self._channel, self._up)
        time.sleep(0.8)
        self.arm_home()

    def close(self) -> None:
        try:
            self.arm_home()
        except Exception:
            pass
