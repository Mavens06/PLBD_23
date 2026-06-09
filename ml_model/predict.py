"""Hybrid crop recommendation inference for Agri-Botics.

The production robot model classifies the **10 Moroccan target crops**
(Blé, Tomate, Oignon, …) from the **4 sensor variables actually measured**
by the RS485 4-in-1 probe: pH, humidity, temperature, **EC**.

Priority:
1. Production model (`ml_model/best_model.pkl` + `scaler.pkl`): 4 features
   (pH, humidity, temperature, EC), 10 target crops. This is the default.
2. Embedded experimental model (`ml_model/models/embedded_model.pkl`):
   3 features (no EC), trained on the public Kaggle crop dataset whose
   classes are tropical crops *outside* the project's 10-crop perimeter.
   **Disabled by default** — it is research/audit only and would break
   agronomic coherence (e.g. recommending "coffee" for Moroccan soil).
   Enable explicitly with `USE_EMBEDDED_MODEL=1`.
3. Rules engine fallback.

Rules always remain active as an agronomic guardrail.
"""

from __future__ import annotations

import json
import logging
import os
import pickle
from pathlib import Path

import pandas as pd
from typing import List

try:
    from .model_registry import EMBEDDED_FEATURES, EMBEDDED_METADATA_PATH, EMBEDDED_MODEL_PATH, LEGACY_MODEL_PATH, LEGACY_SCALER_PATH
    from .rules.engine import Measurement, rank_crops, salinity_alert, top_k as rules_top_k
except ImportError:
    from model_registry import EMBEDDED_FEATURES, EMBEDDED_METADATA_PATH, EMBEDDED_MODEL_PATH, LEGACY_MODEL_PATH, LEGACY_SCALER_PATH
    from rules.engine import Measurement, rank_crops, salinity_alert, top_k as rules_top_k

_log = logging.getLogger(__name__)

# The embedded Kaggle model uses 3 features (no EC) and tropical crop labels
# outside the 10-crop perimeter. It is kept for research but must be opted into
# explicitly so the production path stays on the legitimate 4-feature model.
_EMBEDDED_ENABLED = os.getenv("USE_EMBEDDED_MODEL", "0").strip().lower() in {"1", "true", "yes"}

_EMBEDDED_CACHE = None
_LEGACY_CACHE = None


def _artifact_mtime(path: Path) -> float:
    return path.stat().st_mtime


def _load_embedded():
    global _EMBEDDED_CACHE
    mt = _artifact_mtime(EMBEDDED_MODEL_PATH)
    if _EMBEDDED_CACHE is not None and _EMBEDDED_CACHE[0] == mt:
        return _EMBEDDED_CACHE[1]
    with EMBEDDED_MODEL_PATH.open("rb") as f:
        model = pickle.load(f)
    _EMBEDDED_CACHE = (mt, model)
    return model


def _load_legacy():
    global _LEGACY_CACHE
    import joblib
    mtimes = (_artifact_mtime(LEGACY_MODEL_PATH), _artifact_mtime(LEGACY_SCALER_PATH))
    if _LEGACY_CACHE is not None and _LEGACY_CACHE[:2] == mtimes:
        return _LEGACY_CACHE[2], _LEGACY_CACHE[3]
    model = joblib.load(LEGACY_MODEL_PATH)
    scaler = joblib.load(LEGACY_SCALER_PATH)
    _LEGACY_CACHE = (mtimes[0], mtimes[1], model, scaler)
    return model, scaler


def _rules_scores(m: Measurement) -> dict[str, float]:
    return {s.crop: float(s.score) for s in rank_crops(m)}


def _guardrail_adjust(top: list[dict], m: Measurement) -> tuple[list[dict], list[str]]:
    rules = _rules_scores(m)
    alerts = []
    adjusted = []
    for item in top:
        crop = item["crop"]
        ml_score = float(item.get("score", 0.0))
        rule_score = rules.get(crop)
        final_score = ml_score
        details = dict(item.get("details") or {})
        if rule_score is not None:
            details["rules_score"] = round(rule_score, 1)
            # Soft guardrail: heavily inconsistent ML proposals are penalized,
            # not silently removed, so the explanation remains auditable.
            if rule_score < 45 and ml_score > 50:
                final_score = round((ml_score * 0.65) + (rule_score * 0.35), 1)
                alerts.append(f"{crop}: score agronomique faible ({rule_score:.0f}/100), recommandation pénalisée.")
        adjusted.append({**item, "score": round(final_score, 1), "details": details})
    adjusted.sort(key=lambda x: x["score"], reverse=True)
    return adjusted, alerts


def _alerts(m: Measurement) -> list[str]:
    alerts = []
    if salinity_alert(m):
        alerts.append("EC légèrement élevée : surveiller la salinité.")
    if m.ph < 5.5:
        alerts.append("pH bas : sol acide, correction possible avant cultures sensibles.")
    elif m.ph > 8.0:
        alerts.append("pH élevé : sol alcalin, surveiller la disponibilité des nutriments.")
    if m.humidity < 35:
        alerts.append("Humidité faible : irrigation ou paillage à envisager.")
    elif m.humidity > 90:
        alerts.append("Humidité très élevée : risque d'excès d'eau et de drainage insuffisant.")
    if m.temperature < 10 or m.temperature > 38:
        alerts.append("Température du sol hors plage courante : adapter la date de semis/plantation.")
    return alerts


def _explanation(top: list[dict], engine: str, m: Measurement) -> str:
    if not top:
        return "Aucune culture n'a pu être classée; le moteur de règles reste disponible comme garde-fou."
    crop = top[0]["crop"]
    return (
        f"{crop} est proposée par {engine}; le score final combine la probabilité ML "
        "sur température, humidité et pH avec un contrôle agronomique incluant aussi l'EC mesurée."
    )


def _rules_result(m: Measurement, k: int) -> dict:
    top = [s.as_dict() for s in rules_top_k(m, k=k)]
    return {
        "engine": "rules",
        "top": top,
        "recommendations": [{"crop": t["crop"], "score": round(t["score"] / 100.0, 3)} for t in top],
        "alerts": _alerts(m),
        "explanation": _explanation(top, "le moteur de règles", m),
        "score_source": "rules",
    }


def _embedded_top(model, m: Measurement, k: int) -> list[dict]:
    values = {
        "temperature": m.temperature,
        "humidity": m.humidity,
        "ph": m.ph,
        "ec": m.ec,
    }
    X = pd.DataFrame([[values[f] for f in EMBEDDED_FEATURES]], columns=EMBEDDED_FEATURES)
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)[0]
        classes = list(model.classes_)
        ranked = sorted(zip(classes, probs), key=lambda c: c[1], reverse=True)
        return [{"crop": str(c), "score": round(float(p) * 100, 1), "details": {"ml_probability": round(float(p), 4)}} for c, p in ranked[:k]]
    pred = model.predict(X)[0]
    return [{"crop": str(pred), "score": 100.0, "details": {"ml_probability": None}}]


def _legacy_top(m: Measurement, k: int) -> list[dict]:
    model, scaler = _load_legacy()
    X = [[m.ph, m.humidity, m.temperature, m.ec]]
    X_scaled = scaler.transform(X)
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X_scaled)[0]
        classes = list(model.classes_)
        ranked = sorted(zip(classes, probs), key=lambda c: c[1], reverse=True)
        return [{"crop": str(c), "score": round(float(p) * 100, 1), "details": {"ml_probability": round(float(p), 4)}} for c, p in ranked[:k]]
    pred = model.predict(X_scaled)[0]
    return [{"crop": str(pred), "score": 100.0, "details": {"ml_probability": None}}]


def predict_top_crops(ph: float, humidity: float, temperature: float, ec: float, k: int = 3) -> dict:
    m = Measurement(ph=ph, humidity=humidity, temperature=temperature, ec=ec)
    engine = "rules"
    model_type = "rules"
    top = None

    # 1. Production model: 4 sensor features (incl. EC), 10 target crops.
    if LEGACY_MODEL_PATH.exists() and LEGACY_SCALER_PATH.exists():
        try:
            top = _legacy_top(m, k)
            engine = "ml"
            model_type = "production"
        except Exception as err:
            _log.warning("Production ML unavailable (%s); trying fallback.", err)

    # 2. Embedded experimental model (opt-in only): 3 features, tropical crops.
    if top is None and _EMBEDDED_ENABLED and EMBEDDED_MODEL_PATH.exists():
        try:
            top = _embedded_top(_load_embedded(), m, k)
            engine = "ml"
            model_type = "embedded"
        except Exception as err:
            _log.warning("Embedded ML unavailable (%s); fallback rules.", err)

    if top is None:
        return _rules_result(m, k)

    top, guardrail_alerts = _guardrail_adjust(top, m)
    # Ensure top-3 even if the ML model returned fewer labels.
    existing = {item["crop"] for item in top}
    for score in rules_top_k(m, k=k):
        if len(top) >= k:
            break
        if score.crop not in existing:
            top.append(score.as_dict())
            existing.add(score.crop)
    top = top[:k]
    alerts = _alerts(m) + guardrail_alerts
    return {
        "engine": engine,
        "top": top,
        "recommendations": [{"crop": t["crop"], "score": round(float(t["score"]) / 100.0, 3)} for t in top],
        "alerts": alerts,
        "explanation": _explanation(top, engine, m),
        "score_source": "ML + rules" if engine == "ml" else "rules",
        "model_type": model_type,
    }


def explain(ph: float, humidity: float, temperature: float, ec: float) -> dict:
    m = Measurement(ph=ph, humidity=humidity, temperature=temperature, ec=ec)
    result = {
        "engine": "rules",
        "ranking": [s.as_dict() for s in rank_crops(m)],
        "alerts": _alerts(m),
    }
    result["ml_top"] = predict_top_crops(ph=ph, humidity=humidity, temperature=temperature, ec=ec).get("top", [])
    return result


if __name__ == "__main__":
    print(json.dumps(predict_top_crops(ph=6.7, humidity=62, temperature=23, ec=1.1), ensure_ascii=False, indent=2))
