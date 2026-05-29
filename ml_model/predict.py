"""
predict.py — Point d'entrée d'inférence ML pour le projet PLBD.

Comportement :
  • Si ml_model/best_model.pkl ET ml_model/scaler.pkl existent → on charge
    le modèle Scikit-Learn et on l'utilise.
  • Sinon (cas par défaut tant que train.py n'a pas été lancé) → on bascule
    automatiquement sur le moteur de règles (rules.engine), qui produit
    des scores déterministes.

Cette stratégie évite toute exception si le modèle n'est pas entraîné :
le système fournit toujours une recommandation.

Périmètre :
  Le capteur 4-en-1 RS485 mesure pH, humidité, température, EC. Il n'y a
  PAS de N/P/K dans le pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from .rules.engine import Measurement, top_k as rules_top_k, salinity_alert, rank_crops


_log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_MODEL_PATH = _HERE / "best_model.pkl"
_SCALER_PATH = _HERE / "scaler.pkl"


def _ml_model_available() -> bool:
    return _MODEL_PATH.exists() and _SCALER_PATH.exists()


def _load_ml():
    """Charge le modèle et le scaler. Appelé uniquement si dispo."""
    import joblib   # import paresseux : pas requis si fallback rules
    model = joblib.load(_MODEL_PATH)
    scaler = joblib.load(_SCALER_PATH)
    return model, scaler


def predict_top_crops(
    ph: float,
    humidity: float,
    temperature: float,
    ec: float,
    k: int = 3,
) -> dict:
    """
    Renvoie une recommandation top-k de cultures pour une mesure donnée.

    Mapping sémantique (cohérent avec le code historique du repo) :
      • conductivity / ec     → "salinity" côté features ML
      • moisture / humidity   → "humidity" côté features ML

    Returns
    -------
    {
      "engine":  "ml" | "rules",
      "top":     [{"crop": "...", "score": 0-100, "details": {...}}, ...],
      "alerts":  ["salinity_high", ...],   # liste d'alertes éventuelles
    }
    """
    m = Measurement(ph=ph, humidity=humidity, temperature=temperature, ec=ec)
    alerts: List[str] = []
    if salinity_alert(m):
        alerts.append("salinity_high")

    if _ml_model_available():
        try:
            model, scaler = _load_ml()
            # Convention features attendue par train.py — adaptable si évolution :
            #   [ph, humidity, temperature, salinity]
            X = [[m.ph, m.humidity, m.temperature, m.ec]]
            X_scaled = scaler.transform(X)
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(X_scaled)[0]
                classes = list(model.classes_)
                ranked = sorted(zip(classes, probs), key=lambda c: c[1], reverse=True)
                top = [
                    {"crop": c, "score": round(float(p) * 100, 1), "details": {}}
                    for c, p in ranked[:k]
                ]
            else:
                # Modèle sans proba : on prend la prédiction unique en top-1
                pred = model.predict(X_scaled)[0]
                top = [{"crop": str(pred), "score": 100.0, "details": {}}]
            return {"engine": "ml", "top": top, "alerts": alerts}
        except Exception as err:
            # En cas de modèle corrompu / version incompatible, on retombe sur
            # les règles (la démo ne casse jamais) MAIS on le signale : un modèle
            # cassé ne doit pas passer inaperçu (cf. revue de code, finding #6).
            _log.warning(
                "Inférence ML indisponible (%s) — repli sur le moteur de règles.",
                err,
            )

    top = [s.as_dict() for s in rules_top_k(m, k=k)]
    return {"engine": "rules", "top": top, "alerts": alerts}


def explain(ph: float, humidity: float, temperature: float, ec: float) -> dict:
    """
    Renvoie le classement complet avec détail PAR VARIABLE (debug / UI).

    Le détail par variable est par nature une explication du moteur de RÈGLES
    (le ML n'expose pas de score par variable) : `engine` reflète donc toujours
    "rules" pour le champ `ranking`. Si un modèle ML est disponible, on ajoute
    `ml_top` (cohérent avec /api/recommendation) pour comparaison — sans laisser
    croire que le `ranking` détaillé vient du ML (cf. revue de code, finding #2).
    """
    m = Measurement(ph=ph, humidity=humidity, temperature=temperature, ec=ec)
    result = {
        "engine": "rules",
        "ranking": [s.as_dict() for s in rank_crops(m)],
        "alerts": ["salinity_high"] if salinity_alert(m) else [],
    }
    if _ml_model_available():
        result["ml_top"] = predict_top_crops(
            ph=ph, humidity=humidity, temperature=temperature, ec=ec,
        ).get("top", [])
    return result
