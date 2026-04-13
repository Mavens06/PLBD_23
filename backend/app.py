"""
app.py – Backend FastAPI d'Agribotics tournant sur la Raspberry Pi.

Séparation des responsabilités :
  • La Raspberry Pi exécute le modèle ML Scikit-Learn localement et lit les
    capteurs physiques.  Tout le traitement lourd reste sur l'appareil.
  • La route /api/chat transmet les données capteurs déjà calculées et la
    prédiction ML locale à l'IA cloud pour produire une réponse en langage
    naturel dans la langue choisie (français, arabe ou darija marocaine).
"""

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chatbot_llm import generate_expert_response

# ---------------------------------------------------------------------------
# Création de l'application FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(title="Agribotics API")

# Configuration CORS : lit les origines autorisées depuis la variable
# d'environnement CORS_ORIGINS (liste séparée par des virgules).
# Valeur par défaut : "*" (toutes origines). À restreindre en production
# via CORS_ORIGINS=http://192.168.x.x:8080 dans le fichier .env.
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
    message: str                        # Question de l'agriculteur (texte ou transcription vocale)
    language: str = "fr"               # Langue cible : "fr" | "ar" | "da"
    sensor_data: Optional[dict] = None  # Lectures des capteurs de la Raspberry Pi (optionnel)
    ml_prediction: Optional[str] = None # Recommandation de culture calculée localement (optionnel)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    """Vérifie que le serveur est en cours d'exécution."""
    return {"message": "Agribotics backend is running"}


@app.post("/api/chat")
def chat(request: ChatRequest):
    """
    Reçoit la question de l'agriculteur ainsi que les données capteurs de la
    Raspberry Pi et la prédiction ML locale, puis retourne une réponse experte
    et concise de l'IA cloud dans la langue choisie (fr / ar / da).

    L'IA cloud est utilisée UNIQUEMENT pour humaniser la sortie – le traitement
    réel des données et la recommandation de culture sont effectués entièrement
    sur la Raspberry Pi.
    """
    # Validation de la langue demandée
    if request.language not in ("fr", "ar", "da"):
        raise HTTPException(
            status_code=400,
            detail="Langue non supportée. Utilisez 'fr', 'ar', ou 'da'.",
        )

    # Appel au module LLM cloud pour générer la réponse en langage naturel
    answer = generate_expert_response(
        message=request.message,
        language=request.language,
        sensor_data=request.sensor_data,
        ml_prediction=request.ml_prediction,
    )
    return {"response": answer}
