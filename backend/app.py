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

from fastapi import Depends, FastAPI, HTTPException, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

try:
    from .chatbot_llm import generate_expert_response, synthesize_speech, GEMINI_MODEL, GEMINI_BASE_URL, GEMINI_FALLBACK_MODEL
    from .state import APP_STATE, Measurement, MissionPoint
    from .weather_service import get_forecast
except ImportError:
    # Fallback quand le module est exécuté depuis le dossier backend/ directement
    from chatbot_llm import generate_expert_response, synthesize_speech, GEMINI_MODEL, GEMINI_BASE_URL, GEMINI_FALLBACK_MODEL
    from state import APP_STATE, Measurement, MissionPoint
    from weather_service import get_forecast

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
# Starlette neutralise SILENCIEUSEMENT la combinaison invalide
# allow_origins=["*"] + allow_credentials=True. En mode wildcard on désactive
# donc explicitement les credentials ; sinon (origines listées) on les autorise.
_allow_credentials = "*" not in _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Authentification simple par clé API (opt-in)
# ---------------------------------------------------------------------------
# Pour un robot physique sur un réseau, les routes qui MODIFIENT l'état (POST :
# pilotage mission, push de mesures, chat, tts) ne doivent pas être ouvertes à
# tous. Si AGRIBOTICS_API_KEY est défini dans .env, ces routes exigent l'en-tête
# `X-API-Key`. Si la variable est vide (défaut), l'authentification est
# DÉSACTIVÉE — la démo/dev fonctionne sans clé, comportement inchangé.
_API_KEY = os.getenv("AGRIBOTICS_API_KEY", "").strip()
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(provided: Optional[str] = Security(_api_key_header)) -> None:
    """Dépendance FastAPI : exige X-API-Key sur les routes POST si une clé est configurée."""
    if not _API_KEY:
        return  # auth désactivée (aucune clé configurée) → routes ouvertes
    if provided != _API_KEY:
        raise HTTPException(status_code=401, detail="Clé API invalide ou manquante (en-tête X-API-Key).")


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
    """Mesure transmise par la Raspberry Pi (capteur 4-en-1 RS485).

    Les bornes physiques rejettent (422) les lectures aberrantes d'un capteur
    défaillant, qui pollueraient sinon recommandations et chatbot.
    """
    point: str                                       # Label du point (ex. A1, P3…)
    humidity: float = Field(ge=0, le=100)            # Humidité (%)
    ph: float = Field(ge=0, le=14)                   # pH
    temp: float = Field(ge=-20, le=60)               # Température (°C)
    ec: float = Field(ge=0, le=20)                   # EC / salinité (mS/cm)
    quality: str = "good"


class MissionPointIn(BaseModel):
    """Un point de mesure défini depuis l'interface."""
    label: str                              # Identité du point (ex. "P1")
    x: float                                # Coordonnée X (mètres)
    y: float                                # Coordonnée Y (mètres)


class MissionPlanIn(BaseModel):
    """Plan de mission : liste ordonnée de points à mesurer."""
    points: list[MissionPointIn]


def _first_not_none(*values):
    """Renvoie la première valeur non-None (sans piège du falsy-zero d'`or`)."""
    for v in values:
        if v is not None:
            return v
    return None


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
        "llm_fallback_model": GEMINI_FALLBACK_MODEL or None,
        "llm_endpoint": GEMINI_BASE_URL,
    }


@app.get("/health")
def health():
    """Healthcheck minimal et stable pour la supervision/démo (jamais d'effet de bord)."""
    return {"status": "ok", "service": "agribotics-backend"}


@app.get("/api/status")
def api_status():
    """
    État consolidé du système pour la démo/supervision :
    mission, mode applicatif, dernière mesure, dernière recommandation, LLM.
    Ne lève jamais d'exception — sert aussi de plan B (`curl /api/status`).
    """
    r = APP_STATE.robot
    latest = APP_STATE.latest()

    last_recommendation = None
    if latest is not None:
        try:
            reco = predict_top_crops(
                ph=latest.ph, humidity=latest.humidity,
                temperature=latest.temp, ec=latest.ec, k=3,
            )
            top = reco.get("top") or []
            last_recommendation = {
                "point": latest.point,
                "engine": reco.get("engine"),
                "model_type": reco.get("model_type"),
                "top": [{"crop": t["crop"], "score": t["score"]} for t in top],
                "alerts": reco.get("alerts", []),
            }
        except Exception:
            last_recommendation = None

    return {
        "mission_status": r.status,
        "active_point": r.active_point,
        "progress_pct": r.progress_pct,
        "command": APP_STATE.command,
        "app_mode": os.getenv("APP_MODE", "mock"),
        "measured_points": APP_STATE.measured_points,
        "total_points": APP_STATE.total_points,
        "last_measurement": latest.as_dict() if latest else None,
        "last_recommendation": last_recommendation,
        "llm": {
            "provider": "gemini (google ai studio)",
            "model": GEMINI_MODEL,
            "fallback_model": GEMINI_FALLBACK_MODEL or None,
            "configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        },
    }


@app.get("/api/weather")
async def get_weather(lat: Optional[float] = None, lon: Optional[float] = None):
    """
    Bulletin météo 3 jours (Open-Meteo, sans clé) + consigne d'irrigation dérivée.
    Sert à AFFINER les recommandations : pluie prévue → irrigation reportée/réduite.
    Enrichissement optionnel : renvoie {"available": false} si réseau indisponible.
    """
    return await get_forecast(lat, lon)


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


@app.post("/api/chat", dependencies=[Depends(require_api_key)])
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

    if not (request.message or "").strip():
        raise HTTPException(status_code=400, detail="Message vide.")

    # Si le frontend a envoyé zone_data mais pas sensor_data, on dérive
    # sensor_data depuis zone_data (mapping ec → salinity, temp → temperature).
    sensor_data = request.sensor_data
    if sensor_data is None and request.zone_data:
        zd = request.zone_data
        sensor_data = {
            "pH": _first_not_none(zd.get("ph"), zd.get("pH")),
            "humidity": zd.get("humidity"),
            "temperature": _first_not_none(zd.get("temp"), zd.get("temperature")),
            "salinity": _first_not_none(zd.get("ec"), zd.get("salinity")),
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


class TTSRequest(BaseModel):
    text: str                               # Texte à lire à voix haute
    language: str = "ar"                    # Langue (informatif ; la voix suit le texte)


@app.post("/api/tts", dependencies=[Depends(require_api_key)])
async def tts(request: TTSRequest):
    """
    Synthèse vocale via le modèle TTS de **Gemini** (cloud) : renvoie un WAV
    24 kHz mono. Sert à offrir une vraie voix arabe naturelle, indépendante des
    voix TTS locales du navigateur (souvent absentes pour l'arabe sous Chrome).
    En cas d'échec (quota, réseau), renvoie 503 → le frontend retombe sur la
    synthèse vocale locale.
    """
    if not (request.text or "").strip():
        raise HTTPException(status_code=400, detail="Texte vide.")
    try:
        audio = await synthesize_speech(request.text, request.language)
    except RuntimeError as err:
        raise HTTPException(status_code=503, detail=str(err))
    return Response(content=audio, media_type="audio/wav")


# ---------------------------------------------------------------------------
# Mission & mesures (consommées par frontend_real_backend)
# ---------------------------------------------------------------------------

@app.get("/api/mission")
def get_mission():
    """État courant de la mission : robot + progression + plan + commande."""
    r = APP_STATE.robot
    return {
        "robot": {
            "status": r.status,
            "active_point": r.active_point,
            "progress_pct": r.progress_pct,
        },
        "command": APP_STATE.command,
        "measured_points": APP_STATE.measured_points,
        "total_points": APP_STATE.total_points,
        "zones": APP_STATE.point_ids,
        "plan": [p.as_dict() for p in APP_STATE.plan],
    }


@app.get("/api/mission/plan")
def get_mission_plan():
    """Plan de mission courant (récupéré par le robot pour exécution)."""
    return {"points": [p.as_dict() for p in APP_STATE.plan]}


@app.post("/api/mission/plan", dependencies=[Depends(require_api_key)])
def set_mission_plan(payload: MissionPlanIn):
    """
    Définit le plan de mission depuis l'interface : liste de points (label, x, y).
    Réinitialise l'état mission. C'est ce plan que le robot va exécuter.
    """
    try:
        APP_STATE.set_plan(
            [MissionPoint(label=p.label, x=p.x, y=p.y) for p in payload.points]
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return {"ok": True, "points": [p.as_dict() for p in APP_STATE.plan]}


@app.post("/api/mission/start", dependencies=[Depends(require_api_key)])
def start_mission():
    """
    Commande le démarrage de la mission (déclenchée par l'interface).
    Le robot, en mode --watch, détecte `command=="requested"` et exécute le plan.
    """
    APP_STATE.reset()
    APP_STATE.command = "requested"
    APP_STATE.robot.status = "requested"
    return {"ok": True, "command": APP_STATE.command,
            "total_points": APP_STATE.total_points}


@app.post("/api/mission/end", dependencies=[Depends(require_api_key)])
def end_mission():
    """Demande l'arrêt de la mission en cours (abort)."""
    APP_STATE.command = "idle"
    if APP_STATE.robot.status not in ("done",):
        APP_STATE.robot.status = "idle"
    return {"ok": True, "command": APP_STATE.command}


@app.post("/api/mission/stop", dependencies=[Depends(require_api_key)])
def stop_mission():
    """
    ARRÊT D'URGENCE. Passe la commande à `idle` : le robot (mode --watch) le
    détecte entre deux points et stoppe immédiatement la mission en cours.
    Marque l'état robot `emergency_stop` pour l'affichage. Doit rester fiable
    et sans effet de bord destructeur (les mesures déjà prises sont conservées).
    """
    APP_STATE.command = "idle"
    if APP_STATE.robot.status not in ("done",):
        APP_STATE.robot.status = "emergency_stop"
    return {"ok": True, "command": APP_STATE.command, "robot_status": APP_STATE.robot.status}


@app.post("/api/mission/reset", dependencies=[Depends(require_api_key)])
def reset_mission():
    """Réinitialise l'état mission/mesures en mémoire (conserve le plan)."""
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


@app.post("/api/measurements", dependencies=[Depends(require_api_key)])
def post_measurement(payload: MeasurementIn):
    """
    Enregistre une mesure du capteur 4-en-1 RS485 et met à jour la mission.
    Cette route est appelée par la Raspberry Pi (ou par des outils de démo).
    """
    if not APP_STATE.has_point(payload.point):
        raise HTTPException(
            status_code=400,
            detail=f"Point inconnu : {payload.point}. Plan : {APP_STATE.point_ids}.",
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
    if not APP_STATE.has_point(point):
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
    if not APP_STATE.has_point(point):
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
    if not APP_STATE.has_point(point):
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
