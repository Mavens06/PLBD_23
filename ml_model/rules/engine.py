"""
engine.py — Moteur de règles agronomiques pour recommandation de culture.

Calcule un score pondéré [0, 100] de compatibilité entre une mesure de sol
(4 variables : pH, humidité, température, EC) et chaque culture cible.

Pondérations :
  • pH           × 0.30
  • humidité     × 0.30
  • température  × 0.20
  • EC (salinité)× 0.20

Le moteur de règles sert de :
  • Vérité terrain agronomique (toujours appelable, déterministe).
  • Fallback du modèle ML quand best_model.pkl n'est pas disponible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .crop_catalog import CROP_CATALOG, CropProfile, all_crops, get


WEIGHTS = {"ph": 0.30, "humidity": 0.30, "temperature": 0.20, "ec": 0.20}


@dataclass
class Measurement:
    """Mesure du capteur 4-en-1 RS485 utilisée par le moteur de règles."""
    ph: float
    humidity: float
    temperature: float
    ec: float

    def as_dict(self) -> dict:
        return {"ph": self.ph, "humidity": self.humidity,
                "temperature": self.temperature, "ec": self.ec}


@dataclass
class CropScore:
    crop: str
    score: float                   # [0, 100]
    details: dict                  # score par variable, pour debug/UI

    def as_dict(self) -> dict:
        return {"crop": self.crop, "score": round(self.score, 1),
                "details": {k: round(v, 1) for k, v in self.details.items()}}


def _variable_score(value: float, lo: float, hi: float) -> float:
    """
    Score [0, 100] d'une variable par rapport à sa plage [lo, hi].
    Saturé : 100 à l'intérieur, décroissance linéaire à l'extérieur,
    avec une pente calibrée sur l'amplitude de la plage.
    """
    if lo <= value <= hi:
        return 100.0
    width = max(hi - lo, 1e-6)
    if value < lo:
        return max(0.0, 100.0 - 100.0 * (lo - value) / width)
    return max(0.0, 100.0 - 100.0 * (value - hi) / width)


def score_crop(m: Measurement, profile: CropProfile) -> CropScore:
    """Score d'une mesure pour une culture donnée."""
    parts = {
        "ph":          _variable_score(m.ph,          *profile.ph),
        "humidity":    _variable_score(m.humidity,    *profile.humidity),
        "temperature": _variable_score(m.temperature, *profile.temperature),
        "ec":          _variable_score(m.ec,          *profile.ec),
    }
    score = sum(WEIGHTS[k] * parts[k] for k in WEIGHTS)
    return CropScore(crop=profile.name, score=score, details=parts)


def rank_crops(m: Measurement, candidates: Optional[Iterable[str]] = None) -> List[CropScore]:
    """Trie les cultures par score décroissant."""
    names = list(candidates) if candidates else all_crops()
    scores = [score_crop(m, get(n)) for n in names]
    scores.sort(key=lambda s: s.score, reverse=True)
    return scores


def top_k(m: Measurement, k: int = 3) -> List[CropScore]:
    """Top-k cultures recommandées."""
    return rank_crops(m)[:k]


def salinity_alert(m: Measurement) -> bool:
    """True si l'EC dépasse 2.5 mS/cm (seuil partagé avec le frontend)."""
    return m.ec > 2.5
