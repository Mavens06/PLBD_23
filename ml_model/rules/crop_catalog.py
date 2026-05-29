"""
crop_catalog.py — Paramètres agronomiques des cultures cibles du projet PLBD.

Seules 4 variables sont mesurées par le capteur 4-en-1 RS485 :
  • pH du sol
  • humidité du sol (%)
  • température du sol (°C)
  • conductivité électrique (EC, mS/cm) — proxy de la salinité

N/P/K ne sont JAMAIS utilisés (hors périmètre du capteur).

Les plages indiquent l'intervalle agronomique acceptable issu de la
littérature. Au-delà de ec_max, on signale une alerte salinité.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


Range = Tuple[float, float]


@dataclass(frozen=True)
class CropProfile:
    name: str
    category: str
    ph: Range
    humidity: Range            # en %
    temperature: Range         # en °C
    ec: Range                  # en mS/cm
    compost_kg_per_m2: float   # apport organique de référence


# 10 cultures cibles, cohérent avec frontend/data_model.js.
CROP_CATALOG: Dict[str, CropProfile] = {
    "Blé":              CropProfile("Blé",              "céréale",       (6.0, 7.5), (50, 75), (15, 25), (0.2, 2.5), 0.8),
    "Tomate":           CropProfile("Tomate",           "maraîchage",    (6.0, 6.8), (60, 85), (21, 24), (0.2, 2.0), 1.2),
    "Oignon":           CropProfile("Oignon",           "maraîchage",    (6.0, 7.0), (70, 85), (15, 25), (0.2, 1.5), 1.0),
    "Carotte":          CropProfile("Carotte",          "maraîchage",    (5.0, 6.5), (70, 80), (15, 22), (0.2, 1.2), 0.8),
    "Pomme de terre":   CropProfile("Pomme de terre",   "maraîchage",    (5.0, 6.5), (70, 80), (15, 22), (0.2, 1.7), 1.1),
    "Orge":             CropProfile("Orge",             "céréale",       (6.0, 8.0), (50, 70), (15, 25), (0.2, 3.0), 0.7),
    "Betterave à sucre":CropProfile("Betterave à sucre","industrielle",  (6.5, 8.0), (60, 80), (15, 25), (0.2, 3.5), 1.1),
    "Olivier":          CropProfile("Olivier",          "arboriculture", (6.5, 8.5), (40, 65), (15, 30), (0.2, 3.0), 0.6),
    "Vigne":            CropProfile("Vigne",            "arboriculture", (5.5, 7.5), (50, 70), (18, 30), (0.2, 2.5), 0.6),
    "Pastèque":         CropProfile("Pastèque",         "maraîchage",    (6.0, 7.0), (70, 85), (22, 35), (0.2, 2.0), 1.3),
}


def all_crops() -> list[str]:
    return list(CROP_CATALOG.keys())


def get(name: str) -> CropProfile:
    if name not in CROP_CATALOG:
        raise KeyError(f"Culture inconnue : {name}. Connues : {all_crops()}.")
    return CROP_CATALOG[name]
