"""
base.py — Interfaces de la couche robot/sonde d'Agribotics.

Cette couche **isole le déplacement physique et la sonde** du reste du système
(backend, ML, capteur). C'est l'argument défendable en soutenance :

    « L'acquisition réelle et le déplacement sont isolés dans des couches
      dédiées. Aujourd'hui le robot exécute toute la chaîne de mission en mode
      mock contrôlé ; passer au matériel ne demande qu'à implémenter ces
      interfaces, sans toucher au backend, au moteur de recommandation ni à
      l'interface. »

Deux abstractions :
  • RobotController : déplacement du châssis (Adeept PiCar Pro).
  • ProbeController : descente/remontée de la sonde multi-capteurs.

Le capteur de mesure (RS485 4-en-1) reste géré séparément par
`raspberry_pi/sensors/` (déjà isolé via build_sensor()). Cette couche-ci ne
fait QUE bouger : elle ne lit aucune grandeur physico-chimique.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class RobotController(ABC):
    """Pilotage du déplacement du châssis. Implémentations : mock / adeept."""

    @abstractmethod
    def forward(self, speed: int = 50, duration: float = 1.0) -> None:
        """Avance pendant `duration` secondes à la vitesse `speed` (0-100)."""

    @abstractmethod
    def backward(self, speed: int = 50, duration: float = 1.0) -> None:
        """Recule pendant `duration` secondes à la vitesse `speed` (0-100)."""

    @abstractmethod
    def turn_left(self, speed: int = 40, duration: float = 1.0) -> None:
        """Tourne à gauche pendant `duration` secondes."""

    @abstractmethod
    def turn_right(self, speed: int = 40, duration: float = 1.0) -> None:
        """Tourne à droite pendant `duration` secondes."""

    @abstractmethod
    def stop(self) -> None:
        """Arrêt immédiat des moteurs. DOIT être fiable (arrêt d'urgence)."""

    @abstractmethod
    def move_to_point(self, x: float, y: float) -> None:
        """
        Se rend au point (x, y) en mètres. La planification de trajectoire fine
        (ordre de visite, évitement) n'est pas l'objet de cette V1 : le robot
        visite les points dans l'ordre fourni par le plan de mission.
        """

    def close(self) -> None:
        """Libère les ressources matérielles (GPIO/PWM). No-op par défaut."""


class ProbeController(ABC):
    """Pilotage de la sonde multi-capteurs (servo). Implémentations : mock / adeept."""

    @abstractmethod
    def lower_probe(self) -> None:
        """Descend la sonde dans le sol."""

    @abstractmethod
    def stabilize(self, seconds: float = 3.0) -> None:
        """Attend la stabilisation des lectures (contact sol/sonde)."""

    @abstractmethod
    def raise_probe(self) -> None:
        """Remonte la sonde avant le déplacement suivant."""

    def close(self) -> None:
        """Libère les ressources matérielles (PWM). No-op par défaut."""
