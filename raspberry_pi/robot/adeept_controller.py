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
les rotations par DÉFAUT sont des MANŒUVRES EN 3 POINTS (`TURN_MODE=kturn`) —
avance braqué puis recul contre-braqué, répété jusqu'à l'angle : vraie rotation
quasi sur place où les roues ROULENT (pas de raclage) → le MOINS de dérapage,
adaptée au SABLE. Modes alternatifs : `pivot` (rotation différentielle sur
place) et `arc` (virage en arc, qui fait avancer/déraper). Le gyroscope mesure
l'angle (90°/180°) ; sans gyro, le k-turn reste chronométré (toujours sans
dérapage).

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
        # Throttles SIGNÉS validés au sol : avant = -0.25 (échelon direct, sans
        # rampe — la rampe anti-brownout faisait dévier à gauche au départ),
        # virage = +0.18.
        self._drive_throttle = _envf("DRIVE_THROTTLE", -0.25)
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
        # En mode PULSÉ, c'est la vitesse MOYENNE des segments avant (avec
        # pauses) qui doit être renseignée ici — sinon les distances sont fausses.
        self._speed_mps = _envf("ROBOT_SPEED_MPS", 0.19)
        # Vitesse du RECUL de compensation (au crawl, throttle -DRIVE_THROTTLE),
        # découplée de l'avant qui peut être pulsé/plus rapide. Défaut = ROBOT_SPEED_MPS.
        self._reverse_speed = _envf("REVERSE_SPEED_MPS", self._speed_mps)
        # Échelle plan→physique (démo sur surface réduite). 1.0 = grandeur réelle.
        self._world_scale = max(0.01, _envf("ROBOT_WORLD_SCALE", 1.0))
        # Emprise PHYSIQUE maximale du parcours : côté du carré (m) que le robot
        # ne doit JAMAIS dépasser, quelle que soit la taille du plan édité à la
        # main. Défaut 0.9 m → ≤ 0.81 m² (marge de sécurité sous le 1 m²).
        # fit_to_field() abaisse au besoin _world_scale pour tenir dans ce carré.
        self._max_field_m = max(0.1, _envf("ROBOT_MAX_FIELD_M", 0.9))

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
        # Équilibrage des 2 moteurs de propulsion (dérive en ligne droite due à
        # une asymétrie moteur, pas au braquage). + = booste le moteur droit
        # (corrige une dérive vers la DROITE). Plage utile ≈ [-0.4, 0.4].
        self._drive_balance = max(-0.8, min(0.8, _envf("DRIVE_BALANCE", 0.0)))
        # Boost ADDITIF d'un seul moteur (throttle units), efficace à BASSE
        # vitesse là où le multiplicatif est sans effet (zone plate près du
        # seuil) : + accélère le moteur DROIT (corrige une dérive à droite) en
        # laissant le gauche à sa valeur — donc sans risque de le faire caler.
        self._drive_balance_add = max(-0.5, min(0.5, _envf("DRIVE_BALANCE_ADD", 0.0)))
        # Maintien de cap au gyroscope pendant les lignes droites (annule la
        # dérive résiduelle que le trim seul ne corrige pas). Opt-in : si la
        # correction AGGRAVE la dérive, le signe est inversé sur ce châssis →
        # mettre HEADING_HOLD_SIGN=-1.
        self._heading_hold = os.getenv("HEADING_HOLD", "0").strip().lower() \
            in ("1", "true", "yes")
        self._heading_kp = _envf("HEADING_HOLD_KP", 2.0)
        self._heading_sign = 1.0 if _envf("HEADING_HOLD_SIGN", 1.0) >= 0 else -1.0
        self._heading_max_corr = _envf("HEADING_HOLD_MAX_DEG", 25.0)
        # Suiveur de ligne VIRTUEL : « ligne » = cap initial, écart mesuré par le
        # gyro, correction PID. Kp seul = comportement actuel (P) ; Ki annule
        # l'écart résiduel du biais mécanique ; Kd amortit (anti-oscillation).
        # Ki/Kd à 0 par défaut → logique inchangée, activables par .env.
        self._heading_ki = _envf("HEADING_KI", 0.0)
        self._heading_kd = _envf("HEADING_KD", 0.0)
        self._heading_debug = os.getenv("HEADING_DEBUG", "0").strip().lower() \
            in ("1", "true", "yes")
        # Correction de cap par MINI-COUPS DE VOLANT discrets (feedforward) :
        # pendant la ligne droite, toutes les STRAIGHT_NUDGE_EVERY_S, on braque
        # brièvement (STRAIGHT_NUDGE_S) de STRAIGHT_NUDGE_DEG puis on recentre.
        # + = coups à GAUCHE (corrige une dérive à droite). Stable (pas de
        # boucle) et efficace au pas (braquage franc, pas un micro-trim).
        self._straight_nudge = os.getenv("STRAIGHT_NUDGE", "0").strip().lower() \
            in ("1", "true", "yes")
        self._nudge_every = max(0.2, _envf("STRAIGHT_NUDGE_EVERY_S", 1.5))
        self._nudge_s = max(0.05, _envf("STRAIGHT_NUDGE_S", 0.25))
        self._nudge_deg = _envf("STRAIGHT_NUDGE_DEG", 30.0)
        # Mode PULSÉ (STRAIGHT_PULSE) : on roule par à-coups à PULSE_THROTTLE
        # (régime contrôlable, hors zone morte) entrecoupés de pauses, pour
        # garder une vitesse MOYENNE lente tout en gardant l'autorité de
        # braquage et la lisibilité gyro. Le maintien de cap agit PENDANT
        # chaque impulsion, avec anti-emballement. C'est la parade au mur de la
        # zone morte (au crawl ni braquage ni équilibrage ne mordent).
        self._straight_pulse = os.getenv("STRAIGHT_PULSE", "0").strip().lower() \
            in ("1", "true", "yes")
        self._pulse_throttle = _envf("PULSE_THROTTLE", -0.12)
        self._pulse_on_s = max(0.1, _envf("PULSE_ON_S", 0.4))
        self._pulse_off_s = max(0.0, _envf("PULSE_OFF_S", 0.8))
        # Mode SUIVEUR DE LIGNE VIRTUEL CONTINU (STRAIGHT_MODE=line ou LINE_FOLLOW=1).
        # Le segment courant EST la ligne : roulage CONTINU (rampes de
        # démarrage/arrêt → zéro à-coup, contrairement au pulsé) et redressement
        # PERMANENT pour rester centré. Asservissement combiné, style Stanley :
        #   • erreur de CAP   = ∫ gyro            (°)
        #   • écart LATÉRAL   = ∫ v·sin(cap)      (m, dead-reckoning)
        #   corr = Kp·cap + Kcross·écart + Kd·taux. Throttle CONTINU dans le
        # régime contrôlable (hors zone morte) → autorité de braquage réelle.
        # Prioritaire sur le mode pulsé.
        self._line_follow = os.getenv("STRAIGHT_MODE", "").strip().lower() == "line" \
            or os.getenv("LINE_FOLLOW", "0").strip().lower() in ("1", "true", "yes")
        self._line_throttle = _envf("LINE_THROTTLE", self._pulse_throttle)
        self._line_kp = _envf("LINE_KP", max(0.1, self._heading_kp))
        self._line_kcross = _envf("LINE_KCROSS", 80.0)        # ° de braquage par m d'écart
        self._line_cross_clamp = abs(_envf("LINE_CROSS_CLAMP", 0.15))  # m (borne anti-windup)
        self._line_ramp_s = max(0.0, _envf("LINE_RAMP_S", 0.3))
        # DIFFÉRENTIEL de correction (« roue à gauche / roue à droite ») : à
        # basse vitesse le braquage du servo avant n'a AUCUNE autorité (les roues
        # avant braquées ne font pas tourner le châssis au crawl). Le différentiel
        # moteur, lui, fait pivoter le robot à TOUTE vitesse. On module donc les
        # 2 moteurs proportionnellement à la correction : fraction du throttle de
        # base transférée d'une roue à l'autre à pleine correction. 0 = désactivé.
        self._line_diff = max(0.0, min(0.9, _envf("LINE_DIFF", 0.0)))
        # Manœuvre en 3 points (TURN_MODE=kturn) : durée d'une impulsion
        # avant/arrière braquée. Plus court = empreinte plus petite, plus de
        # va-et-vient ; plus long = rotation plus rapide, empreinte plus large.
        self._kturn_pulse_s = _envf("KTURN_PULSE_S", 0.5)
        # Repli CHRONOMÉTRÉ du k-turn (gyro absent) : nombre d'allers-retours
        # (avant braqué + arrière contre-braqué) pour un quart de tour (90°).
        # 180° = ×2. À calibrer au sol si le robot tourne sans gyroscope.
        self._kturn_cycles_90 = max(1, _envi("KTURN_CYCLES_90", 3))
        # Throttle (magnitude) des impulsions du k-turn — séparé de la ligne
        # droite : celle-ci tourne lentement pour la précision (DRIVE_THROTTLE
        # bas), mais le k-turn doit rouler franchement pour ne pas caler.
        self._kturn_throttle = abs(_envf("KTURN_THROTTLE", 0.15))
        # Recul de compensation APRÈS un virage en ARC (gyro) : l'arc fait
        # avancer le robot ; on recule de cette distance pour revenir sur le
        # point. Préféré à la déduction sur la ligne droite suivante (qui échoue
        # quand la ligne est courte ou orientée autrement). À calibrer au sol.
        self._turn_backup_m = _envf("TURN_BACKUP_M", 0.0)
        # Facteur appliqué à la distance d'un segment qui suit IMMÉDIATEMENT un
        # virage (1.0 = inchangé). Resserre le serpentin / compense l'avance du
        # pivot. Demandé par Marius : 0.5 (moitié après chaque virage).
        self._post_turn_scale = max(0.0, _envf("POST_TURN_LEG_SCALE", 1.0))

        # --- Initialisation matérielle --------------------------------------
        i2c = busio.I2C(board.SCL, board.SDA)
        self._pca = PCA9685(i2c, address=self._addr)
        self._pca.frequency = self._freq
        self._left = _motor.DCMotor(self._pca.channels[m1a], self._pca.channels[m1b])
        self._right = _motor.DCMotor(self._pca.channels[m2a], self._pca.channels[m2b])
        # SLOW_DECAY (mode roue libre lente) — validé sur le robot de Marius :
        # à bas throttle les moteurs tournent en douceur et gardent du couple,
        # au lieu de brouter/caler (FAST_DECAY par défaut). Indispensable pour
        # le suiveur de ligne continu à basse vitesse (anti-zone-morte).
        try:
            self._left.decay_mode = _motor.SLOW_DECAY
            self._right.decay_mode = _motor.SLOW_DECAY
        except Exception as err:
            _log(f"⚠ decay_mode non réglable ({err})")

        # Cache des objets Servo (1 par canal) : éviter d'en recréer un à CHAQUE
        # _set_angle (le suiveur appelle ~50 Hz) — moins de trafic I2C, bus plus sûr.
        self._servos: dict[int, object] = {}

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
        # TURN_MODE=kturn (DÉFAUT) : MANŒUVRE EN 3 POINTS (avant braqué ↔ arrière
        # contre-braqué) — vraie rotation quasi sur place, roues qui ROULENT (pas
        # de raclage) → le MOINS de dérapage, idéale sur SABLE · TURN_MODE=pivot :
        # rotation sur place (moteurs G/D opposés, peut racler les roues) ·
        # TURN_MODE=arc : virage en arc (avance d'arc géométrique, dérape sur sable).
        # Avec gyro : on tourne jusqu'à l'angle MESURÉ (90°/180°), indépendant des
        # batteries et du sol. Sans gyro : k-turn CHRONOMÉTRÉ (toujours sans
        # dérapage) ; les autres modes retombent sur l'arc chronométré.
        self._turn_mode = os.getenv("TURN_MODE", "kturn").strip().lower()
        self._pivot_throttle = abs(_envf("PIVOT_THROTTLE", 0.15))
        self._pivot_invert = os.getenv("PIVOT_INVERT", "0").strip().lower() \
            in ("1", "true", "yes")
        # Compensation de TRANSLATION pendant le pivot, PAR SENS. Un pivot idéal
        # est une rotation PURE (centre fixe) ; en pratique l'asymétrie des
        # moteurs (forces avant/arrière inégales) fait « glisser » le robot dans
        # un sens. Ce trim est une composante COMMUNE ajoutée aux deux roues :
        # elle décale le robot pour annuler la dérive SANS changer la vitesse de
        # rotation (le différentiel gauche−droite reste intact). Signe : valeur
        # POSITIVE = pousse vers l'ARRIÈRE (sur ce câblage avant = throttle
        # négatif) → corrige un robot qui AVANCE pendant le pivot ; négative =
        # corrige un robot qui RECULE. Réglé par sens car la dérive diffère
        # entre pivot droite et gauche. 0 = pivot brut (comportement d'origine).
        self._pivot_trim_right = max(-0.5, min(0.5, _envf("PIVOT_TRIM_RIGHT", 0.0)))
        self._pivot_trim_left = max(-0.5, min(0.5, _envf("PIVOT_TRIM_LEFT", 0.0)))
        # Recul de compensation APRÈS une rotation, PAR SENS : la rotation fait
        # « avancer » le robot d'un petit résidu (le trim de pivot ne l'annule
        # pas toujours entièrement). On RACCOURCIT d'autant la ligne droite qui
        # suit la rotation (et, à défaut de segment suffisant, on recule du
        # reliquat). Mis à l'échelle selon l'angle (90° → ×1, demi-tour → ×2).
        # En mètres PHYSIQUES (le résidu est une distance réelle au sol) : déduit
        # directement de la distance physique du segment, PAS de l'échelle plan.
        self._post_turn_right_backup_m = max(0.0, _envf("POST_TURN_RIGHT_BACKUP_M", 0.0))
        self._post_turn_left_backup_m = max(0.0, _envf("POST_TURN_LEFT_BACKUP_M", 0.0))
        self._pending_turn_backup_m = 0.0   # rempli par _turn_to selon le sens
        # Forcer les demi-tours À GAUCHE (activé temporairement au retour home).
        self._prefer_left_turns = False
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
             f"balance={self._drive_balance:+.2f}/{self._drive_balance_add:+.2f}, "
             f"cap={'hold' if self._heading_hold and self._gyro else 'libre'}, "
             f"nudge={'on' if self._straight_nudge else 'off'}, "
             f"pulse={'on' if self._straight_pulse else 'off'}, "
             f"line={'on' if self._line_follow else 'off'})")

    # -- Bas niveau ----------------------------------------------------------
    def _i2c_write(self, fn, retries: int = 3) -> None:
        """Écriture I2C TOLÉRANTE aux glitches : sous charge moteur, le PCA peut
        renvoyer un « Remote I/O error » (Errno 121) transitoire (micro-creux de
        tension). On retente quelques fois ; en dernier recours on IGNORE — un
        glitch ponctuel ne doit JAMAIS tuer la mission (la boucle réémet la
        consigne au tour suivant). Résilience terrain, comme le buffer hors-ligne."""
        for attempt in range(retries):
            try:
                fn()
                return
            except OSError as err:
                if attempt == retries - 1:
                    _log(f"⚠ I2C : glitch ignoré après {retries} essais ({err})")
                    return
                time.sleep(0.008)

    def _set_angle(self, channel: int, angle: float) -> None:
        """Positionne un servo (miroir exact du set_angle validé), objet mis en
        cache et écriture I2C tolérante aux glitches."""
        s = self._servos.get(channel)
        if s is None:
            from adafruit_motor import servo
            s = servo.Servo(self._pca.channels[channel], min_pulse=500,
                            max_pulse=2400, actuation_range=180)
            self._servos[channel] = s
        val = max(0.0, min(180.0, float(angle)))
        self._i2c_write(lambda: setattr(s, "angle", val))

    def _throttle(self, value: float) -> None:
        """Avance/recul des DEUX moteurs, avec ÉQUILIBRAGE (DRIVE_BALANCE) :
        si les 2 moteurs ne tournent pas exactement à la même vitesse, le robot
        dérive en ligne droite. `+balance` accélère le moteur DROIT (corrige une
        dérive vers la droite) ; `-balance` accélère le gauche. Plus efficace
        que le trim de braquage quand la cause est une asymétrie des moteurs."""
        value = max(-1.0, min(1.0, value))
        b = self._drive_balance
        left = value * (1.0 - b)
        right = value * (1.0 + b)
        # Boost additif d'un seul moteur (sens = direction de marche, pour
        # AUGMENTER la magnitude sans inverser ni caler l'autre moteur).
        a = self._drive_balance_add
        if a != 0.0 and value != 0.0:
            s = -1.0 if value < 0 else 1.0      # +magnitude = même signe que la marche
            if a > 0:
                right += s * abs(a)             # booste la droite
            else:
                left += s * abs(a)              # booste la gauche
        lv = max(-1.0, min(1.0, left))
        rv = max(-1.0, min(1.0, right))
        self._i2c_write(lambda: setattr(self._left, "throttle", lv))
        self._i2c_write(lambda: setattr(self._right, "throttle", rv))

    def _throttle_lr(self, left: float, right: float) -> None:
        """Commande différentielle (pivot sur place / correction du suiveur)."""
        lv = max(-1.0, min(1.0, left))
        rv = max(-1.0, min(1.0, right))
        self._i2c_write(lambda: setattr(self._left, "throttle", lv))
        self._i2c_write(lambda: setattr(self._right, "throttle", rv))

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
        # Suiveur de ligne virtuel CONTINU (prioritaire) : roulage fluide +
        # redressement permanent pour rester centré sur la ligne.
        if self._line_follow and correct_heading:
            self._drive_line_follow(duration, check_obstacles)
            return
        # Mode pulsé : délègue (roule par à-coups en régime contrôlable).
        if self._straight_pulse and correct_heading:
            self._drive_pulsed(duration, check_obstacles)
            return
        center = self._steer_center + self._steer_trim
        self._set_angle(self._steer_ch, center)
        hold = self._heading_hold and self._gyro is not None and correct_heading
        nudge = self._straight_nudge and correct_heading and not hold
        fine = hold or nudge
        remaining = max(0.0, duration)
        heading_dev = 0.0                       # dérive de cap intégrée (°)
        i_acc = 0.0                             # intégrale de l'écart (terme I)
        i_clamp = (self._heading_max_corr / self._heading_ki) if self._heading_ki > 0 else 0.0
        since_obstacle = 0.0
        since_debug = 0.0
        since_nudge = 0.0
        nudge_left = 0.0                         # temps restant du coup de volant
        last = time.monotonic()
        self._throttle(throttle)
        while remaining > 0:
            dt = min(0.05 if fine else 0.4, remaining)
            time.sleep(dt)
            remaining -= dt
            now = time.monotonic()
            elapsed = now - last
            if hold:
                rate = self._gyro.rate_dps()
                heading_dev += rate * elapsed
                # Anti-emballement : on borne la dérive intégrée pour qu'elle
                # puisse REVENIR quand le taux s'inverse (sinon windup → blocage
                # en saturation, cf. essai à −0.09).
                dev_clamp = self._heading_max_corr / max(0.1, self._heading_kp)
                heading_dev = max(-dev_clamp, min(dev_clamp, heading_dev))
                i_acc += heading_dev * elapsed
                if i_clamp:
                    i_acc = max(-i_clamp, min(i_clamp, i_acc))   # anti-windup I
                corr = self._heading_pid(heading_dev, rate, i_acc)
                self._set_angle(self._steer_ch, center - corr)
                since_debug += elapsed
                if self._heading_debug and since_debug >= 0.3:
                    since_debug = 0.0
                    _log(f"cap: taux={rate:+.1f}°/s dev={heading_dev:+.1f}° "
                         f"corr={corr:+.1f}° → braquage={center - corr:.0f}°")
            elif nudge:
                if nudge_left > 0:               # coup de volant en cours
                    nudge_left -= elapsed
                    if nudge_left <= 0:
                        self._set_angle(self._steer_ch, center)   # redressement
                else:
                    since_nudge += elapsed
                    if since_nudge >= self._nudge_every:
                        since_nudge = 0.0
                        nudge_left = self._nudge_s
                        # + = gauche (braquage vers 0° = self._steer_left)
                        target = center - self._nudge_deg
                        self._set_angle(self._steer_ch, target)
                        if self._heading_debug:
                            _log(f"nudge gauche {self._nudge_deg:.0f}° "
                                 f"({self._nudge_s:.2f}s) → braquage={target:.0f}°")
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

    def _heading_pid(self, dev: float, rate: float, i_acc: float) -> float:
        """Correction PID du suiveur de ligne virtuel (cible : écart de cap = 0).
        dev = écart de cap (∫taux), rate = taux courant (terme D), i_acc = ∫dev.
        Renvoie l'angle de correction (borné), signe châssis appliqué."""
        corr = self._heading_sign * (
            self._heading_kp * dev
            + self._heading_ki * i_acc
            + self._heading_kd * rate
        )
        return max(-self._heading_max_corr, min(self._heading_max_corr, corr))

    def _drive_pulsed(self, duration: float, check_obstacles: bool = True) -> None:
        """
        Ligne droite par À-COUPS : impulsions à PULSE_THROTTLE (régime
        contrôlable, hors zone morte) séparées de pauses → vitesse MOYENNE
        lente, mais autorité de braquage et lisibilité gyro conservées. Le
        maintien de cap (gyro) agit pendant chaque impulsion, avec anti-windup.
        La distance dépend de la vitesse MOYENNE : caler ROBOT_SPEED_MPS dessus.
        """
        center = self._steer_center + self._steer_trim
        self._set_angle(self._steer_ch, center)
        hold = self._gyro is not None
        heading_dev = 0.0
        i_acc = 0.0
        dev_clamp = self._heading_max_corr / max(0.1, self._heading_kp)
        i_clamp = (self._heading_max_corr / self._heading_ki) if self._heading_ki > 0 else 0.0
        end = time.monotonic() + max(0.0, duration)
        n_pulse = 0
        corr = 0.0
        while time.monotonic() < end:
            if check_obstacles:
                self._ensure_path_clear()
            # --- impulsion ON (régime contrôlable) ---
            self._throttle(self._pulse_throttle)
            last = time.monotonic()
            on_end = min(end, last + self._pulse_on_s)
            while time.monotonic() < on_end:
                time.sleep(0.04)
                now = time.monotonic()
                if hold:
                    dt2 = now - last
                    rate = self._gyro.rate_dps()
                    heading_dev += rate * dt2
                    heading_dev = max(-dev_clamp, min(dev_clamp, heading_dev))
                    i_acc += heading_dev * dt2
                    if i_clamp:
                        i_acc = max(-i_clamp, min(i_clamp, i_acc))   # anti-windup I
                    corr = self._heading_pid(heading_dev, rate, i_acc)
                    self._set_angle(self._steer_ch, center - corr)
                last = now
            n_pulse += 1
            if self._heading_debug:
                _log(f"pulse #{n_pulse}: dev={heading_dev:+.1f}° "
                     f"corr={corr:+.1f}° braquage={center - corr:.0f}°")
            # --- pause OFF (vitesse moyenne basse ; pas d'intégration à l'arrêt) ---
            self._throttle(0.0)
            self._set_angle(self._steer_ch, center)
            off_end = min(end, time.monotonic() + self._pulse_off_s)
            while time.monotonic() < off_end:
                time.sleep(0.04)
        # Frein actif + arrêt franc.
        if self._brake_pulse_s > 0:
            self._throttle(-self._pulse_throttle * 0.6)
            time.sleep(self._brake_pulse_s)
        self._throttle(0.0)

    def _ramp_throttle(self, start: float, target: float, secs: float) -> None:
        """Rampe LINÉAIRE de throttle sur `secs` (anti-à-coup au départ/arrêt)."""
        if secs <= 0:
            self._throttle(target)
            return
        steps = max(1, int(secs / 0.03))
        for i in range(1, steps + 1):
            self._throttle(start + (target - start) * i / steps)
            time.sleep(secs / steps)

    def _drive_line_follow(self, duration: float, check_obstacles: bool = True) -> None:
        """
        SUIVEUR DE LIGNE VIRTUEL CONTINU. Le segment courant EST la ligne :
        le robot roule EN CONTINU (démarrage/arrêt en rampe → zéro à-coup) et se
        redresse en PERMANENCE pour rester CENTRÉ sur la ligne. Asservissement
        combiné (style Stanley), cible : écart de cap ET écart latéral = 0 :
          • cap   = ∫ gyro                 → erreur angulaire vs la ligne (°)
          • écart = ∫ v·sin(cap)·dt        → décalage latéral estimé (m)
          corr = Kp·cap + Kcross·écart + Kd·taux  (borné, signe châssis appliqué).
        À la différence du crawl continu (zone morte → gyro aveugle, braquage
        sans autorité), on roule à LINE_THROTTLE, dans le régime contrôlable.
        """
        import math
        center = self._steer_center + self._steer_trim
        self._set_angle(self._steer_ch, center)
        hold = self._gyro is not None
        v = abs(self._speed_mps) or 0.1
        heading_dev = 0.0          # erreur de cap intégrée (°)
        cross = 0.0                # écart latéral estimé (m)
        dev_clamp = self._heading_max_corr / max(0.1, self._line_kp)
        end = time.monotonic() + max(0.0, duration)
        corr = 0.0
        n = 0
        # Démarrage en rampe douce (anti-à-coup) puis croisière continue.
        self._ramp_throttle(0.0, self._line_throttle, self._line_ramp_s)
        last = time.monotonic()
        while time.monotonic() < end:
            if check_obstacles:
                self._ensure_path_clear()
            time.sleep(0.02)
            now = time.monotonic()
            dt = now - last
            last = now
            if hold:
                rate = self._gyro.rate_dps()
                heading_dev += rate * dt
                heading_dev = max(-dev_clamp, min(dev_clamp, heading_dev))
                cross += v * math.sin(math.radians(heading_dev)) * dt
                cross = max(-self._line_cross_clamp, min(self._line_cross_clamp, cross))
                err = heading_dev + self._line_kcross * cross
                corr = self._heading_sign * (self._line_kp * err
                                             + self._heading_kd * rate)
                corr = max(-self._heading_max_corr, min(self._heading_max_corr, corr))
                self._set_angle(self._steer_ch, center - corr)
                # DIFFÉRENTIEL : à basse vitesse le volant ne mord pas, mais une
                # roue plus lente que l'autre fait pivoter le robot. On RALENTIT
                # SEULEMENT la roue intérieure (jamais accélérer l'extérieure
                # au-delà de la base) → vitesse PLAFONNÉE à la base (pas de
                # survitesse, pas de roue qui cale pendant que l'autre s'emballe),
                # et tourner ralentit le robot (bon pour rester précis). corr>0 =
                # redressement à GAUCHE → on ralentit la roue GAUCHE.
                if self._line_diff > 0:
                    d = self._line_diff * (corr / self._heading_max_corr)  # signé
                    base = self._line_throttle
                    if d >= 0:   # tourner à gauche : ralentir la roue gauche
                        self._throttle_lr(base * (1.0 - d), base)
                    else:        # tourner à droite : ralentir la roue droite
                        self._throttle_lr(base, base * (1.0 + d))
            n += 1
            if self._heading_debug and n % 15 == 0:
                _log(f"ligne: cap={heading_dev:+.1f}° écart={cross * 100:+.1f}cm "
                     f"corr={corr:+.1f}° braquage={center - corr:.0f}°")
        # Arrêt en rampe douce + frein léger (toujours sans à-coup).
        self._ramp_throttle(self._line_throttle, 0.0, self._line_ramp_s)
        self._set_angle(self._steer_ch, center)
        if self._brake_pulse_s > 0:
            self._throttle(-self._line_throttle * 0.4)
            time.sleep(self._brake_pulse_s)
        self._throttle(0.0)

    def _reverse_distance(self, dist_m: float) -> None:
        """Recule en ligne droite d'une distance donnée (sans maintien de cap :
        la géométrie de braquage s'inverse en marche arrière). Sert à annuler
        l'avance provoquée par un virage en arc."""
        if dist_m <= 0 or self._reverse_speed <= 0:
            return
        duration = dist_m / self._reverse_speed
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

    def _turn_kturn_timed(self, target_deg: float, clockwise: bool) -> None:
        """
        K-turn CHRONOMÉTRÉ — repli SANS gyroscope (garde la manœuvre 3 points
        sans dérapage au lieu de retomber sur l'arc, qui dérape sur sable).
        Le nombre d'allers-retours est calibré pour 90° (KTURN_CYCLES_90), ×2
        pour un demi-tour. Même séquence que la version gyro : avance braqué dans
        le sens du virage, puis recule contre-braqué (annule la translation).
        """
        fwd_steer = self._steer_right if clockwise else self._steer_left
        bwd_steer = self._steer_left if clockwise else self._steer_right
        fwd_t = -self._kturn_throttle   # avant = throttle négatif sur ce câblage
        bwd_t = self._kturn_throttle
        cycles = self._kturn_cycles_90 * (2 if target_deg >= 135 else 1)
        try:
            for _ in range(cycles):
                # 1) avance braqué dans le sens du virage
                self._set_angle(self._steer_ch, fwd_steer)
                time.sleep(0.05)
                self._throttle(fwd_t)
                time.sleep(self._kturn_pulse_s)
                self._throttle(0.0)
                time.sleep(0.12)
                # 2) recule contre-braqué (même sens de rotation, translation annulée)
                self._set_angle(self._steer_ch, bwd_steer)
                time.sleep(0.05)
                self._throttle(bwd_t)
                time.sleep(self._kturn_pulse_s)
                self._throttle(0.0)
                time.sleep(0.12)
        finally:
            self._throttle(0.0)
            try:
                self._set_angle(self._steer_ch, self._steer_center + self._steer_trim)
            except Exception:
                pass
        _log(f"rotation k-turn chronométrée : {cycles} cycles "
             f"(cible {target_deg}°, ~{self._kturn_cycles_90}/90°)")
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
            # Trim de translation (composante COMMUNE, par sens) : annule la
            # dérive du pivot sans toucher au différentiel (donc à la rotation).
            trim = self._pivot_trim_right if clockwise else self._pivot_trim_left
            # avant = throttle négatif sur ce câblage → pivot horaire (droite)
            # = roue gauche en avant (-t), roue droite en arrière (+t)
            if clockwise:
                self._throttle_lr(-t + trim, t + trim)
            else:
                self._throttle_lr(t + trim, -t + trim)
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
        # Sens de rotation : droite (delta 1) / demi-tour (delta 2, HORAIRE par
        # défaut) / gauche (delta 3). Le DEMI-TOUR peut être forcé À GAUCHE
        # (counter-clockwise) via `_prefer_left_turns` — utilisé au RETOUR HOME
        # pour éviter le résidu d'avance des rotations droites (un 180° a deux
        # sens équivalents, contrairement à un quart de tour imposé par la
        # géométrie).
        clockwise = delta in (1, 2)
        if delta == 2 and self._prefer_left_turns:
            clockwise = False
        # Recul de compensation post-rotation, selon le sens RÉEL (après l'éventuel
        # passage à gauche) et l'angle (demi-tour = 2× un quart de tour). Consommé
        # par move_to_point sur la ligne droite qui suit.
        per_quarter = self._post_turn_right_backup_m if clockwise \
            else self._post_turn_left_backup_m
        self._pending_turn_backup_m = per_quarter * (2.0 if delta == 2 else 1.0)
        # Angle à tourner (NE PAS écraser `target`, qui reste la chaîne de cap
        # "N/E/S/W" affectée à self._heading en fin de fonction — sinon un float
        # fuite dans le cap et HEADINGS.index() plante au virage suivant d'un
        # même déplacement en L).
        target_deg = 180.0 if delta == 2 else 90.0
        if self._turn_mode == "kturn":
            # Vraie rotation 3 points (sans dérapage), gyro si dispo sinon chrono.
            if self._gyro is not None:
                self._turn_kturn(target_deg, clockwise)
            else:
                self._turn_kturn_timed(target_deg, clockwise)
        elif self._gyro is not None:
            # pivot / arc asservis au gyro (angle mesuré)
            self._turn_gyro(target_deg, clockwise)
        elif delta == 1:
            self._turn_arc(self._steer_right, self._turn_90_s)
        elif delta == 2:
            self._turn_arc(self._steer_right if clockwise else self._steer_left,
                           self._turn_90_s * 2)
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

    def fit_to_field(self, points) -> None:
        """Borne l'emprise PHYSIQUE du parcours à un carré (`ROBOT_MAX_FIELD_M`).

        Calcule la boîte englobante des points du plan (en mètres-plan), origine
        (0,0) incluse car le robot y démarre et peut y revenir, puis abaisse au
        besoin l'échelle plan→physique pour que le plus grand côté ne dépasse
        pas `ROBOT_MAX_FIELD_M`. **N'augmente jamais** l'échelle configurée : un
        plan qui tient déjà conserve `ROBOT_WORLD_SCALE`. Garantit « jamais
        au-delà du carré » quel que soit le plan édité à la main. Sans effet sur
        l'UI ni les mesures (seule la distance parcourue au sol est réduite)."""
        if not points:
            return
        xs = [0.0] + [float(getattr(p, "x", 0.0)) for p in points]
        ys = [0.0] + [float(getattr(p, "y", 0.0)) for p in points]
        span = max(max(xs) - min(xs), max(ys) - min(ys))
        if span <= 0:
            return
        fit = self._max_field_m / span
        if fit < self._world_scale:
            _log(f"emprise plan {span:.2f} m × échelle {self._world_scale:.4f} "
                 f"dépasse {self._max_field_m} m → échelle bornée à {fit:.4f}")
            self._world_scale = fit

    def prefer_left_turns(self, enable: bool = True) -> None:
        """Force les DEMI-TOURS à se faire par la GAUCHE (counter-clockwise).
        Activé temporairement pour le retour à l'origine (les rotations droites
        gardent un léger résidu d'avance ; passer à gauche l'évite)."""
        self._prefer_left_turns = bool(enable)

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
        # Rotation SUR PLACE (pas d'avance d'arc à compenser) : le k-turn l'est
        # toujours (gyro ou chrono) ; le pivot seulement avec gyro (sinon il
        # retombe sur l'arc, qui avance).
        in_place_turn = (self._turn_mode == "kturn") \
            or (self._gyro is not None and self._turn_mode == "pivot")
        arc_backup = self._turn_mode != "pivot" and self._turn_backup_m > 0
        arc_advance = 0.0 if (in_place_turn or arc_backup) else self._turn_advance_m
        pending_arc_advance = 0.0
        pending_turn_backup = 0.0     # résidu d'avance de la rotation, par sens
        just_turned = False
        for kind, value in legs:
            if kind == "turn":
                self._turn_to(str(value))
                pending_arc_advance = arc_advance
                # Recul de compensation calculé par _turn_to selon le sens/angle :
                # on raccourcit d'autant la ligne droite qui suit (cumul si
                # plusieurs rotations s'enchaînent avant un segment).
                pending_turn_backup += self._pending_turn_backup_m
                just_turned = True
            else:
                dist_plan = float(value)
                dist_phys = dist_plan * self._world_scale
                # Segment qui suit IMMÉDIATEMENT un virage : distance réduite
                # (POST_TURN_LEG_SCALE) — demandé pour resserrer le serpentin et
                # compenser une éventuelle avance résiduelle du pivot.
                if just_turned and self._post_turn_scale != 1.0:
                    dist_phys *= self._post_turn_scale
                    _log(f"segment post-virage : ×{self._post_turn_scale:.2f}")
                just_turned = False
                if pending_arc_advance > 0:
                    comp = min(pending_arc_advance, dist_phys)
                    dist_phys -= comp
                    pending_arc_advance = 0.0
                    _log(f"compensation virage : -{comp:.2f} m (l'arc a déjà avancé)")
                # Recul de compensation post-rotation : on raccourcit ce segment
                # du résidu d'avance de la rotation (distance physique). Le
                # reliquat éventuel (segment plus court que le résidu) est gardé
                # et reculé en fin de déplacement.
                if pending_turn_backup > 0:
                    comp = min(pending_turn_backup, dist_phys)
                    dist_phys -= comp
                    pending_turn_backup -= comp
                    _log(f"compensation post-rotation : -{comp:.2f} m sur le segment")
                duration = dist_phys / self._speed_mps if self._speed_mps > 0 else 0.0
                _log(f"ligne droite {dist_plan:.2f} m plan → {dist_phys:.2f} m réel "
                     f"≈ {duration:.1f}s")
                if duration > 0:
                    self._drive_straight(self._drive_throttle, duration)
                time.sleep(0.2)
        # Politique « avance comme avant » : on ne RECULE JAMAIS après une
        # rotation (le recul perturbait le déplacement). Un éventuel reliquat
        # (segment suivant trop court ou absent) reste simplement non compensé —
        # négligeable en pratique, et préférable à une marche arrière.
        if pending_turn_backup > 0:
            _log(f"compensation post-rotation : reliquat {pending_turn_backup:.2f} m "
                 f"non appliqué (pas de recul)")
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
