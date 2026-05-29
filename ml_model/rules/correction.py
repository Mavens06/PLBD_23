"""
correction.py — Diagnostic du sol et conseils de correction pour une culture cible.

Répond à la question : « J'ai choisi cette culture sur cette zone ; au vu des
4 variables mesurées, mon sol convient-il, et sinon comment le corriger ? »

C'est le complément du moteur de recommandation (engine.py) :
  • engine.py   → « quelle culture planter dans mon sol ? »  (recommandation)
  • correction.py → « comment corriger mon sol pour la culture VOULUE ? » (diagnostic)

Toute la logique est déterministe et adossée aux plages agronomiques de
crop_catalog.py. Le LLM (Gemini) ne fait que reformuler la sortie : il
n'invente aucun conseil. Périmètre strict : pH, humidité, température, EC.
Aucun N/P/K.
"""

from __future__ import annotations

from typing import List, Optional

from .crop_catalog import CropProfile, get
from .engine import Measurement, rank_crops, score_crop


# Libellés et unités d'affichage par variable (ordre stable).
_VAR_LABELS = {
    "ph":          ("pH",          ""),
    "humidity":    ("humidité",    " %"),
    "temperature": ("température",  " °C"),
    "ec":          ("EC/salinité", " mS/cm"),
}

# Conseils de correction déterministes (FR). Gemini les traduit en AR/Darija.
# {compost} est substitué pour le cas "ec trop bas" (fertilité faible).
_ACTIONS = {
    ("ph", "low"):  "Relever le pH : apport d'amendement calcaire (chaux agricole ou dolomie).",
    ("ph", "high"): "Abaisser le pH : apport de soufre élémentaire ou de matière organique "
                    "acidifiante (compost, fumier bien décomposé).",
    ("humidity", "low"):  "Augmenter l'humidité du sol : irrigation (idéalement goutte-à-goutte) "
                          "et paillage pour limiter l'évaporation.",
    ("humidity", "high"): "Réduire l'excès d'eau : améliorer le drainage et espacer les irrigations.",
    ("temperature", "low"):  "Sol trop frais : pailler, décaler le semis vers une période plus "
                             "chaude ou protéger (voile/tunnel).",
    ("temperature", "high"): "Sol trop chaud : pailler pour isoler, ombrer et irriguer aux heures fraîches.",
    ("ec", "low"):  "Fertilité/salinité faible : enrichir le sol avec un apport de compost "
                    "(~{compost} kg/m²).",
    ("ec", "high"): "Salinité excessive : lessivage à l'eau douce, amélioration du drainage et "
                    "réduction des apports d'engrais.",
}


def _status(value: float, lo: float, hi: float) -> str:
    """ok si dans la plage, sinon 'low' (sous le minimum) ou 'high' (au-dessus)."""
    if value < lo:
        return "low"
    if value > hi:
        return "high"
    return "ok"


def diagnose(
    m: Measurement,
    target_crop: str,
    suggest_k: int = 3,
) -> dict:
    """
    Diagnostique l'adéquation du sol `m` pour la culture `target_crop` et
    propose des corrections variable par variable.

    Returns
    -------
    {
      "target_crop": "Olivier",
      "compatibility": 78.5,           # score [0-100] du sol pour cette culture
      "suitable": true|false,          # toutes les variables dans la plage ?
      "diagnostics": [
        {"variable": "ph", "label": "pH", "value": 7.0,
         "range": [6.5, 8.5], "status": "ok", "action": null},
        ...
      ],
      "actions": ["...", ...],         # corrections concrètes (variables hors plage)
      "better_suited": [               # cultures naturellement mieux adaptées au sol
        {"crop": "Orge", "score": 92.0}, ...
      ],
    }
    """
    profile: CropProfile = get(target_crop)
    ranges = {
        "ph": profile.ph,
        "humidity": profile.humidity,
        "temperature": profile.temperature,
        "ec": profile.ec,
    }
    values = {
        "ph": m.ph,
        "humidity": m.humidity,
        "temperature": m.temperature,
        "ec": m.ec,
    }

    diagnostics: List[dict] = []
    actions: List[str] = []
    suitable = True
    for var in ("ph", "humidity", "temperature", "ec"):
        lo, hi = ranges[var]
        val = values[var]
        st = _status(val, lo, hi)
        action: Optional[str] = None
        if st != "ok":
            suitable = False
            tmpl = _ACTIONS[(var, st)]
            action = tmpl.format(compost=profile.compost_kg_per_m2)
            actions.append(action)
        diagnostics.append({
            "variable": var,
            "label": _VAR_LABELS[var][0],
            "value": round(val, 2),
            "range": [lo, hi],
            "status": st,
            "action": action,
        })

    compatibility = round(score_crop(m, profile).score, 1)

    # Complément : cultures naturellement les mieux adaptées au sol tel quel,
    # en excluant la culture cible elle-même.
    better = [
        {"crop": s.crop, "score": round(s.score, 1)}
        for s in rank_crops(m)
        if s.crop != target_crop
    ][:suggest_k]

    return {
        "target_crop": target_crop,
        "compatibility": compatibility,
        "suitable": suitable,
        "diagnostics": diagnostics,
        "actions": actions,
        "better_suited": better,
    }


def diagnosis_to_prompt(diag: dict) -> str:
    """
    Sérialise un diagnostic en bloc de contexte compact pour le prompt LLM.
    Le LLM reçoit des faits déjà calculés ; il ne fait que les reformuler.
    """
    crop = diag["target_crop"]
    lines = [
        f"Diagnostic du sol pour la culture choisie ({crop}) — "
        f"compatibilité {diag['compatibility']}/100 :"
    ]
    for d in diag["diagnostics"]:
        lo, hi = d["range"]
        unit = _VAR_LABELS[d["variable"]][1]
        if d["status"] == "ok":
            lines.append(
                f"- {d['label']} {d['value']}{unit} : OK (plage cible {lo}-{hi}{unit})."
            )
        else:
            sens = "trop bas" if d["status"] == "low" else "trop élevé"
            lines.append(
                f"- {d['label']} {d['value']}{unit} : {sens} (cible {lo}-{hi}{unit}). "
                f"Correction : {d['action']}"
            )
    if diag["better_suited"]:
        alt = ", ".join(b["crop"] for b in diag["better_suited"])
        lines.append(
            f"Cultures naturellement les mieux adaptées à ce sol en l'état : {alt}."
        )
    return "\n".join(lines) + " "
