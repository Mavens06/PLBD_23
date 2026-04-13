"""
app.py – Agribotics FastAPI backend running on the Raspberry Pi.

Responsibility split:
  • The Raspberry Pi runs the Scikit-Learn ML model locally and reads the
    physical sensors.  All heavy data-processing stays on-device.
  • The /chat endpoint forwards the already-computed sensor data and local ML
    prediction to the cloud LLM solely to produce a natural-language answer in
    the farmer's preferred language (French, Arabic, or Moroccan Darija).
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from chatbot_llm import generate_expert_response

app = FastAPI(title="Agribotics API")


# ---------------------------------------------------------------------------
# Request schema for the /chat endpoint
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    user_query: str
    lang: str = "fr"          # "fr" | "ar" | "da"
    sensor_data: dict         # raw sensor readings from the Raspberry Pi
    ml_prediction: str        # crop recommendation computed locally by ML model


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    return {"message": "Agribotics backend is running"}


@app.post("/chat")
def chat(request: ChatRequest):
    """
    Receive the farmer's question together with the Raspberry Pi's local sensor
    readings and ML crop prediction, then return a concise expert response from
    the cloud LLM in the chosen language (fr / ar / da).

    The cloud LLM is used ONLY to humanise the output – the actual data
    processing and crop recommendation are done entirely on the Raspberry Pi.
    """
    if request.lang not in ("fr", "ar", "da"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported language. Use 'fr', 'ar', or 'da'.",
        )

    answer = generate_expert_response(
        user_query=request.user_query,
        lang=request.lang,
        sensor_data=request.sensor_data,
        ml_prediction=request.ml_prediction,
    )
    return {"response": answer}
