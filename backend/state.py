"""
state.py — État applicatif minimal en mémoire pour le backend Agribotics.

Sert à exposer aux frontends "real_backend" :
  • Le plan de mission (liste de points de mesure définis par coordonnées x/y).
  • L'état de la mission (point actif, progression, commande robot).
  • L'historique des mesures du capteur 4-en-1 RS485 par point.

Le plan de mission est DYNAMIQUE : l'interface peut le redéfinir (N points
arbitraires), le robot le récupère et l'exécute. La grille 3×3 historique
(A1..C3) n'est plus qu'un plan par défaut pour que l'app fonctionne dès
l'ouverture et que la démo curée reste reproductible.

Ce singleton reste volontairement simple : l'etat courant vit en memoire, mais
le plan de mission et les mesures sont persistes dans SQLite pour survivre a un
redemarrage du backend. La commande robot reste volatile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from . import persistence
except ImportError:
    import persistence


def _safe_persist(fn, *args) -> None:
    """Ignore les erreurs SQLite pour garder le backend utilisable en memoire."""
    try:
        fn(*args)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Plan de mission par défaut (grille 3×3, espacement 3 m)
# ---------------------------------------------------------------------------
# Labels historiques + coordonnées explicites. Conservés pour que la démo et
# les profils curés du frontend (alerte salinité A1/C1…) restent identiques.
ZONES = ("A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3")

_DEFAULT_SPACING_M = 3.0
_DEFAULT_GRID = [  # (label, col, row) → (x, y) = (col*spacing, row*spacing)
    ("A1", 0, 0), ("A2", 1, 0), ("A3", 2, 0),
    ("B1", 0, 1), ("B2", 1, 1), ("B3", 2, 1),
    ("C1", 0, 2), ("C2", 1, 2), ("C3", 2, 2),
]


@dataclass
class MissionPoint:
    """Un point de mesure du plan : un label et des coordonnées (mètres)."""
    label: str
    x: float
    y: float

    def as_dict(self) -> dict:
        return {"label": self.label, "x": self.x, "y": self.y}


def default_plan() -> List[MissionPoint]:
    """Plan 3×3 par défaut (compatibilité ascendante + démo)."""
    return [
        MissionPoint(label=label, x=col * _DEFAULT_SPACING_M, y=row * _DEFAULT_SPACING_M)
        for label, col, row in _DEFAULT_GRID
    ]


@dataclass
class RobotState:
    # idle | requested | moving | measuring | done | emergency_stop
    status: str = "idle"
    active_point: str = "HOME"
    progress_pct: float = 0.0


@dataclass
class Measurement:
    point: str
    humidity: float
    ph: float
    temp: float
    ec: float                          # EC en mS/cm (salinité / conductivité électrique)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    quality: str = "good"

    def as_dict(self) -> dict:
        return {
            "point": self.point,
            "humidity": self.humidity,
            "ph": self.ph,
            "temp": self.temp,
            "ec": self.ec,
            "salinity": self.ec,   # alias frontend
            "timestamp": self.timestamp,
            "quality": self.quality,
        }


@dataclass
class AppState:
    robot: RobotState = field(default_factory=RobotState)
    plan: List[MissionPoint] = field(default_factory=default_plan)
    command: str = "idle"              # idle | requested | running | done
    measurements_by_zone: Dict[str, Measurement] = field(default_factory=dict)
    history: List[Measurement] = field(default_factory=list)

    # -- Plan ---------------------------------------------------------------
    @property
    def point_ids(self) -> List[str]:
        return [p.label for p in self.plan]

    def has_point(self, label: str) -> bool:
        return label in self.point_ids

    def point(self, label: str) -> Optional[MissionPoint]:
        for p in self.plan:
            if p.label == label:
                return p
        return None

    def set_plan(self, points: List[MissionPoint]) -> None:
        """Remplace le plan de mission et repart d'un état mission vierge."""
        if not points:
            raise ValueError("Le plan de mission doit contenir au moins un point.")
        labels = [p.label for p in points]
        if len(set(labels)) != len(labels):
            raise ValueError("Les labels des points doivent être uniques.")
        self.plan = list(points)
        self.measurements_by_zone.clear()
        self.history.clear()
        self.robot = RobotState()
        self.command = "idle"
        _safe_persist(persistence.replace_plan, [p.as_dict() for p in self.plan])

    # -- Progression --------------------------------------------------------
    @property
    def measured_points(self) -> int:
        return len(self.measurements_by_zone)

    @property
    def total_points(self) -> int:
        return len(self.plan)

    def record_measurement(self, m: Measurement) -> None:
        if not self.has_point(m.point):
            raise ValueError(
                f"Point inconnu : {m.point}. Points du plan : {self.point_ids}."
            )
        self.measurements_by_zone[m.point] = m
        self.history.append(m)
        self.robot.active_point = m.point
        self.robot.progress_pct = round(100 * self.measured_points / self.total_points, 1)
        if self.measured_points >= self.total_points:
            self.robot.status = "done"
            self.command = "done"
        else:
            self.robot.status = "measuring"
        _safe_persist(persistence.save_measurement, m.as_dict())

    def latest(self) -> Optional[Measurement]:
        return self.history[-1] if self.history else None

    def reset(self) -> None:
        """Vide les mesures et l'état robot/commande, mais CONSERVE le plan."""
        self.robot = RobotState()
        self.command = "idle"
        self.measurements_by_zone.clear()
        self.history.clear()
        _safe_persist(persistence.clear_measurements)


# Singleton partagé par toutes les routes.
APP_STATE = AppState()


def _hydrate_from_storage(state: AppState) -> None:
    """Recharge plan et mesures persistés au démarrage du backend."""
    try:
        stored_plan = persistence.load_plan()
        if stored_plan:
            state.plan = [
                MissionPoint(label=str(p["label"]), x=float(p["x"]), y=float(p["y"]))
                for p in stored_plan
            ]

        for raw in persistence.load_measurements():
            m = Measurement(
                point=str(raw["point"]),
                humidity=float(raw["humidity"]),
                ph=float(raw["ph"]),
                temp=float(raw["temp"]),
                ec=float(raw["ec"]),
                timestamp=str(raw["timestamp"]),
                quality=str(raw.get("quality") or "good"),
            )
            if not state.has_point(m.point):
                continue
            state.measurements_by_zone[m.point] = m
            state.history.append(m)

        if state.history:
            latest = state.history[-1]
            state.robot.active_point = latest.point
            state.robot.progress_pct = round(100 * state.measured_points / state.total_points, 1)
            state.robot.status = "done" if state.measured_points >= state.total_points else "measuring"
            state.command = "done" if state.robot.status == "done" else "idle"
    except Exception:
        # Le backend doit rester disponible meme si le fichier SQLite est
        # absent, corrompu ou non accessible. Dans ce cas, on repart en memoire.
        state.robot = RobotState()
        state.command = "idle"
        state.measurements_by_zone.clear()
        state.history.clear()


_hydrate_from_storage(APP_STATE)
