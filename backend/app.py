"""
app.py – Backend FastAPI d'Agribotics tournant sur la Raspberry Pi.

Séparation des responsabilités :
  • La Raspberry Pi exécute le modèle ML Scikit-Learn localement et lit le
    capteur 4-en-1 RS485 (pH, humidité, température, EC/salinité).
    Aucune donnée N/P/K n'est mesurée ni traitée.
  • La route /api/chat transmet les données capteurs déjà calculées et la
    prédiction ML locale au LLM **Gemini** (Google AI Studio) pour produire une
    réponse en langage naturel dans la langue choisie (français, arabe ou darija).

L'inférence ML/règles reste 100% locale. Seule la couche conversationnelle
(/api/chat) appelle le cloud Google et requiert une clé GEMINI_API_KEY.
"""

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from .chatbot_llm import generate_expert_response, GEMINI_MODEL, GEMINI_BASE_URL
    from .state import APP_STATE, Measurement, ZONES
except ImportError:
    # Fallback quand le module est exécuté depuis le dossier backend/ directement
    from chatbot_llm import generate_expert_response, GEMINI_MODEL, GEMINI_BASE_URL
    from state import APP_STATE, Measurement, ZONES

# Le moteur d'inférence ML (ou fallback rules) est dans ml_model/.
# Comme backend/ et ml_model/ sont des packages frères à la racine du projet,
# le fichier doit être lancé depuis la racine ; l'import absolu fonctionne.
from ml_model.predict import predict_top_crops, explain as ml_explain
from ml_model.rules.crop_catalog import CROP_CATALOG
from ml_model.rules.engine import Measurement as RuleMeasurement
from ml_model.rules.correction import diagnose, diagnosis_to_prompt

# ---------------------------------------------------------------------------
# Création de l'application FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(title="Agribotics API")

# Configuration CORS : lit les origines autorisées depuis la variable
# d'environnement CORS_ORIGINS (liste séparée par des virgules).
_cors_origins_env = os.getenv("CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schéma de la requête pour la route /api/chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str                            # Question de l'agriculteur
    language: str = "fr"                    # Langue cible : "fr" | "ar" | "da"
    sensor_data: Optional[dict] = None      # Lectures du capteur 4-en-1 RS485
    ml_prediction: Optional[str] = None     # Recommandation ML locale
    selected_zone: Optional[str] = None     # Zone choisie (ex. "B2")
    selected_crop: Optional[str] = None     # Culture cible (ex. "Tomate")
    zone_data: Optional[dict] = None        # Mesures de la zone sélectionnée
    robot_state: Optional[dict] = None      # État du robot/mission
    history: Optional[list] = None          # Tours précédents [{role, content}] pour le suivi


class MeasurementIn(BaseModel):
    """Mesure transmise par la Raspberry Pi (capteur 4-en-1 RS485)."""
    point: str                              # Zone : A1, A2, ..., C3
    humidity: float                         # Humidité (%)
    ph: float                               # pH
    temp: float                             # Température (°C)
    ec: float                               # Conductivité électrique / salinité (mS/cm)
    quality: str = "good"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    """Vérifie que le serveur est en cours d'exécution."""
    return {
        "message": "Agribotics backend is running",
        "llm_provider": "gemini (google ai studio)",
        "llm_model": GEMINI_MODEL,
        "llm_endpoint": GEMINI_BASE_URL,
    }


def _measurement_from_sensor_data(sensor_data: Optional[dict]) -> Optional[RuleMeasurement]:
    """Construit une mesure règles depuis le dict capteur (clés pH/humidity/
    temperature/salinity). Retourne None si une des 4 variables manque."""
    if not sensor_data:
        return None
    ph = sensor_data.get("pH")
    hum = sensor_data.get("humidity")
    temp = sensor_data.get("temperature")
    ec = sensor_data.get("salinity")
    if None in (ph, hum, temp, ec):
        return None
    return RuleMeasurement(ph=ph, humidity=hum, temperature=temp, ec=ec)


def _build_correction_context(selected_crop: Optional[str], sensor_data: Optional[dict]):
    """Diagnostic de correction sérialisé pour le prompt, ou None si non applicable."""
    if not selected_crop or selected_crop not in CROP_CATALOG:
        return None
    m = _measurement_from_sensor_data(sensor_data)
    if m is None:
        return None
    return diagnosis_to_prompt(diagnose(m, selected_crop))


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Reçoit la question de l'agriculteur ainsi que les données capteurs de la
    Raspberry Pi et la prédiction ML locale, puis retourne une réponse experte
    et concise du LLM **Gemini** (cloud) dans la langue choisie (fr / ar / da).

    Le LLM est utilisé UNIQUEMENT pour humaniser la sortie — le
    traitement réel des données et la recommandation de culture sont effectués
    entièrement sur la Raspberry Pi à partir du capteur 4-en-1 RS485.
    """
    if request.language not in ("fr", "ar", "da"):
        raise HTTPException(
            status_code=400,
            detail="Langue non supportée. Utilisez 'fr', 'ar', ou 'da'.",
        )

    # Si le frontend a envoyé zone_data mais pas sensor_data, on dérive
    # sensor_data depuis zone_data (mapping ec → salinity, temp → temperature).
    sensor_data = request.sensor_data
    if sensor_data is None and request.zone_data:
        zd = request.zone_data
        sensor_data = {
            "pH": zd.get("ph"),
            "humidity": zd.get("humidity"),
            "temperature": zd.get("temp") or zd.get("temperature"),
            "salinity": zd.get("ec") or zd.get("salinity"),
        }
        sensor_data = {k: v for k, v in sensor_data.items() if v is not None}

    # Si l'agriculteur a choisi une culture cible ET qu'on dispose des 4
    # variables du sol, on calcule un diagnostic de correction déterministe
    # (rules.correction) et on l'injecte dans le prompt. Le LLM le reformule
    # sans inventer de conseil.
    correction_context = _build_correction_context(
        request.selected_crop, sensor_data,
    )

    try:
        answer = await generate_expert_response(
            message=request.message,
            language=request.language,
            sensor_data=sensor_data,
            ml_prediction=request.ml_prediction,
            selected_zone=request.selected_zone,
            selected_crop=request.selected_crop,
            robot_state=request.robot_state,
            correction_context=correction_context,
            history=request.history,
        )
    except RuntimeError as err:
        raise HTTPException(status_code=503, detail=str(err))

    return {"response": answer}


# ---------------------------------------------------------------------------
# Mission & mesures (consommées par frontend_real_backend)
# ---------------------------------------------------------------------------

@app.get("/api/mission")
def get_mission():
    """État courant de la mission : robot + progression."""
    r = APP_STATE.robot
    return {
        "robot": {
            "status": r.status,
            "active_point": r.active_point,
            "progress_pct": r.progress_pct,
        },
        "measured_points": APP_STATE.measured_points,
        "total_points": APP_STATE.total_points,
        "zones": list(ZONES),
    }


@app.post("/api/mission/reset")
def reset_mission():
    """Réinitialise l'état mission/mesures en mémoire."""
    APP_STATE.reset()
    return {"ok": True}


@app.get("/api/measurements")
def get_measurements():
    """Renvoie la dernière mesure + l'historique complet par zone."""
    latest = APP_STATE.latest()
    return {
        "latest": latest.as_dict() if latest else None,
        "history": [m.as_dict() for m in APP_STATE.history],
        "by_zone": {z: m.as_dict() for z, m in APP_STATE.measurements_by_zone.items()},
    }


@app.post("/api/measurements")
def post_measurement(payload: MeasurementIn):
    """
    Enregistre une mesure du capteur 4-en-1 RS485 et met à jour la mission.
    Cette route est appelée par la Raspberry Pi (ou par des outils de démo).
    """
    if payload.point not in ZONES:
        raise HTTPException(
            status_code=400,
            detail=f"Point inconnu : {payload.point}. Attendu : {list(ZONES)}.",
        )
    m = Measurement(
        point=payload.point,
        humidity=payload.humidity,
        ph=payload.ph,
        temp=payload.temp,
        ec=payload.ec,
        quality=payload.quality,
    )
    APP_STATE.record_measurement(m)
    return {"ok": True, "measurement": m.as_dict()}


# ---------------------------------------------------------------------------
# Recommandation agronomique (ML ou fallback moteur de règles)
# ---------------------------------------------------------------------------

@app.get("/api/recommendation/{point}")
def get_recommendation(point: str, k: int = 3):
    """
    Renvoie le top-k cultures recommandées pour une zone donnée, à partir
    de la dernière mesure stockée. Si best_model.pkl est présent, c'est le
    modèle ML qui décide ; sinon, le moteur de règles déterministe.
    """
    if point not in ZONES:
        raise HTTPException(status_code=400, detail=f"Point inconnu : {point}.")
    m = APP_STATE.measurements_by_zone.get(point)
    if m is None:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune mesure pour {point}. Lancer la mission d'abord.",
        )
    result = predict_top_crops(ph=m.ph, humidity=m.humidity,
                               temperature=m.temp, ec=m.ec, k=k)
    return {"point": point, "measurement": m.as_dict(), **result}


@app.get("/api/recommendation")
def get_recommendation_all(k: int = 3):
    """Recommandation pour toutes les zones mesurées."""
    items = []
    for point, m in APP_STATE.measurements_by_zone.items():
        r = predict_top_crops(ph=m.ph, humidity=m.humidity,
                              temperature=m.temp, ec=m.ec, k=k)
        items.append({"point": point, "measurement": m.as_dict(), **r})
    return {"items": items, "count": len(items)}


@app.get("/api/recommendation/{point}/explain")
def get_recommendation_explain(point: str):
    """Classement complet (10 cultures) + détail par variable pour debug/UI."""
    if point not in ZONES:
        raise HTTPException(status_code=400, detail=f"Point inconnu : {point}.")
    m = APP_STATE.measurements_by_zone.get(point)
    if m is None:
        raise HTTPException(status_code=404, detail=f"Aucune mesure pour {point}.")
    return {"point": point, "measurement": m.as_dict(),
            **ml_explain(ph=m.ph, humidity=m.humidity,
                         temperature=m.temp, ec=m.ec)}


@app.get("/api/recommendation/{point}/correction")
def get_soil_correction(point: str, crop: str):
    """
    Diagnostic du sol d'une zone pour une culture CIBLE choisie par l'agriculteur.

    Indique, variable par variable, si le sol convient et sinon la correction
    concrète (chaux, soufre, irrigation, drainage…). Ajoute les cultures
    naturellement les mieux adaptées au sol en l'état. Logique 100 % déterministe
    (rules.correction), exposable telle quelle ou reformulée par le chatbot.
    """
    if point not in ZONES:
        raise HTTPException(status_code=400, detail=f"Point inconnu : {point}.")
    if crop not in CROP_CATALOG:
        raise HTTPException(
            status_code=400,
            detail=f"Culture inconnue : {crop}. Connues : {list(CROP_CATALOG)}.",
        )
    m = APP_STATE.measurements_by_zone.get(point)
    if m is None:
        raise HTTPException(status_code=404, detail=f"Aucune mesure pour {point}.")
    rule_m = RuleMeasurement(ph=m.ph, humidity=m.humidity,
                             temperature=m.temp, ec=m.ec)
    return {"point": point, "measurement": m.as_dict(), **diagnose(rule_m, crop)}
