"""
chatbot_llm.py — Couche conversationnelle d'AgriBot propulsée par le LLM
**Gemini** de Google, servi via l'API Google AI Studio (Generative Language API).

Note d'architecture :
  La Raspberry Pi effectue tout le traitement métier :
    • Lecture du capteur 4-en-1 RS485 (pH, humidité, température, EC/salinité).
    • Exécution du modèle Scikit-Learn local (best_model.pkl) ou du moteur de
      règles fallback pour produire une recommandation de culture.

  Ce module n'effectue AUCUN apprentissage automatique ni traitement capteur.
  Sa seule responsabilité est de prendre la prédiction calculée localement et
  les lectures actuelles des capteurs, de les combiner avec la question de
  l'agriculteur, et d'appeler le LLM **Gemini** (cloud Google AI Studio) pour
  générer une réponse naturelle et contextuelle dans la langue choisie
  (français, arabe classique ou darija marocaine).

  Flux de données :
    Capteurs → ML Raspberry Pi → (sensor_data + ml_prediction + message)
      → LLM Gemini (Google AI Studio) → réponse en langage naturel (fr / ar / da)

  IMPORTANT : contrairement à l'inférence ML/règles qui reste 100% locale,
  cette couche conversationnelle appelle un service cloud. Une connexion
  internet et une clé API (GEMINI_API_KEY) sont donc requises. Seuls le
  message de l'agriculteur et le contexte agronomique (4 variables capteur,
  culture recommandée) sont transmis — jamais d'identifiant personnel.
"""

import base64
import io
import json
import os
import re
import wave
from typing import Optional

import httpx
from dotenv import load_dotenv

# Chargement des variables d'environnement depuis le fichier .env à la racine.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Configuration Gemini / Google AI Studio (surchargeable via .env).
# Obtenir une clé gratuite : https://aistudio.google.com/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT", "60"))
# Modèle de repli si le modèle principal renvoie 429 (quota free-tier épuisé).
# Par défaut gemini-2.5-flash-lite, qui dispose d'un quota gratuit plus large.
# Mettre à vide pour désactiver le repli.
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite").strip()

# Synthèse vocale (TTS) Gemini : modèle audio dédié + voix prédéfinie. La voix
# parle automatiquement la langue du texte fourni (arabe, français…). Liste des
# voix : https://ai.google.dev/gemini-api/docs/speech-generation
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts").strip()
GEMINI_TTS_VOICE = os.getenv("GEMINI_TTS_VOICE", "Kore").strip()

# Noms d'affichage des langues utilisés dans le prompt système pour indiquer
# au LLM dans quelle langue répondre.
_LANG_LABELS = {
    "fr": "français",
    "ar": "arabe classique (العربية الفصحى)",
    "da": "darija marocaine (الدارجة المغربية, transcrite en lettres arabes)",
}

# Cultures cibles de la V1 (cohérent avec frontend/data_model.js et
# ml_model/rules/crop_catalog.py). Aucune culture hors-périmètre.
_TARGET_CROPS = (
    "Blé, Tomate, Oignon, Carotte, Pomme de terre, Orge, "
    "Betterave à sucre, Olivier, Vigne, Pastèque"
)

# Champs capteurs autorisés — strictement les 4 variables du capteur 4-en-1 RS485.
# N/P/K sont volontairement exclus : le capteur ne les mesure pas.
_ALLOWED_SENSOR_KEYS = {"pH", "humidity", "temperature", "salinity"}

# Garde-fous d'entrée (défense en profondeur, indépendamment du frontend) :
# borne la longueur du message et le nombre de tours d'historique transmis au
# LLM pour maîtriser le coût/latence et éviter qu'une entrée anormale ne sature
# le budget de tokens.
_MAX_MESSAGE_CHARS = 2000
_MAX_HISTORY_TURNS = 8


def _build_sensor_context(sensor_data: Optional[dict]) -> str:
    """Sérialise les lectures capteur en contexte texte pour le prompt."""
    if not sensor_data:
        return "Aucune donnée capteur disponible pour le moment. "
    safe_data = {
        k: v for k, v in sensor_data.items()
        if k in _ALLOWED_SENSOR_KEYS and isinstance(v, (int, float))
    }
    if not safe_data:
        return "Aucune donnée capteur valide disponible. "
    return (
        "Voici les données actuelles du sol lues par le capteur 4-en-1 RS485 : "
        f"{json.dumps(safe_data, ensure_ascii=False)} "
        "(humidité en %, température en °C, salinité/EC en mS/cm). "
    )


def _build_system_prompt(
    language: str,
    sensor_data: Optional[dict],
    ml_prediction: Optional[str],
    selected_zone: Optional[str],
    selected_crop: Optional[str],
    robot_state: Optional[dict],
    correction_context: Optional[str] = None,
) -> str:
    """Compose un prompt système robuste, ancré sur les données réelles."""
    lang_label = _LANG_LABELS.get(language, _LANG_LABELS["fr"])

    sensor_context = _build_sensor_context(sensor_data)

    if ml_prediction:
        ml_context = (
            "La prédiction locale de culture calculée par notre modèle "
            f"d'Intelligence Artificielle est : {ml_prediction}. "
        )
    else:
        ml_context = ""

    # Diagnostic de correction du sol déjà calculé (déterministe). Le LLM doit
    # s'appuyer dessus sans inventer d'autre conseil agronomique.
    correction_block = (correction_context + " ") if correction_context else ""

    zone_context = f"Zone analysée : {selected_zone}. " if selected_zone else ""
    crop_context = f"Culture cible choisie par l'agriculteur : {selected_crop}. " if selected_crop else ""

    if robot_state and isinstance(robot_state, dict):
        active = robot_state.get("activePoint") or robot_state.get("active_point")
        measured = robot_state.get("measuredPoints") or robot_state.get("measured_points")
        total = robot_state.get("totalPoints") or robot_state.get("total_points")
        robot_context = ""
        if active:
            robot_context += f"Le robot est actuellement au point {active}. "
        if measured is not None and total is not None:
            robot_context += f"Progression de la mission : {measured}/{total} points mesurés. "
    else:
        robot_context = ""

    return (
        "Tu es AgriBot, un expert agricole marocain embarqué sur un robot "
        "Adeept Pi Car équipé d'une Raspberry Pi et d'un capteur industriel "
        "4-en-1 RS485 (Modbus RTU) qui mesure UNIQUEMENT quatre variables du sol : "
        "pH, humidité, température, et conductivité électrique (EC, exprimée en mS/cm, "
        "indicateur de salinité). "
        "IMPORTANT : le capteur ne mesure PAS l'azote (N), le phosphore (P) ni le "
        "potassium (K) — tu n'en connais donc AUCUNE valeur. N'affirme jamais en avoir "
        "mesuré, et ne fonde aucune recommandation d'engrais ni aucun dosage sur N/P/K. "
        "(Tu peux tout au plus évoquer brièvement le rôle d'un nutriment dans une "
        "explication générale, sans prétendre l'avoir mesuré.) "
        f"Les seules cultures cibles à recommander sont : {_TARGET_CROPS}. "
        + sensor_context
        + ml_context
        + zone_context
        + crop_context
        + robot_context
        + correction_block
        + "Tu es un assistant agricole CONVERSATIONNEL : tu comprends n'importe quel "
        "message et tu peux répondre à toute question liée au champ, au sol, aux "
        "cultures, à l'irrigation, aux amendements, aux pratiques agricoles et au robot, "
        "y compris en expliquant en détail quand on te le demande. Règles : "
        "(1) Pour tout ce qui concerne CE sol précis (son état, sa correction, la "
        "culture adaptée), appuie-toi STRICTEMENT sur les mesures et le diagnostic "
        "ci-dessus : n'invente jamais de chiffres ni de mesures, et ne mentionne jamais "
        "N/P/K. "
        "(2) Pour les questions agronomiques générales (bonnes pratiques, comment faire, "
        "pourquoi, quand semer/irriguer/amender…), donne des explications claires et "
        "pédagogiques fondées sur des connaissances agricoles établies. "
        "(3) Adapte la longueur : par défaut 2 à 4 phrases concrètes ; mais si "
        "l'agriculteur demande une explication, un « pourquoi », un « comment » ou plus "
        "de détails, DÉVELOPPE en étapes pratiques simples à appliquer. Même en mode "
        "détaillé, reste SYNTHÉTIQUE : environ 250 mots maximum, 6 points maximum, et "
        "TERMINE toujours par une courte phrase de conclusion (ne laisse jamais une "
        "réponse coupée en milieu de phrase). "
        "(4) Si le message n'a aucun rapport avec l'agriculture ou le champ, réoriente "
        "poliment l'agriculteur vers ton rôle en une phrase, sans le brusquer. "
        "(5) Si une culture mieux adaptée au sol est indiquée, mentionne-la. "
        f"Réponds EXCLUSIVEMENT en {lang_label}, de façon naturelle et respectueuse. "
        "N'explique pas ta nature technique ni ton fonctionnement interne."
    )


async def generate_expert_response(
    message: str,
    language: str,
    sensor_data: Optional[dict] = None,
    ml_prediction: Optional[str] = None,
    selected_zone: Optional[str] = None,
    selected_crop: Optional[str] = None,
    robot_state: Optional[dict] = None,
    correction_context: Optional[str] = None,
    history: Optional[list] = None,
) -> str:
    """
    Génère une réponse agricole courte et experte via le LLM Gemini (cloud).

    L'appel HTTP est asynchrone (httpx.AsyncClient) pour ne pas bloquer la
    boucle évènementielle FastAPI : plusieurs requêtes peuvent être traitées
    en parallèle sans saturer le serveur.

    Paramètres
    ----------
    message : str
        Question de l'agriculteur (texte ou transcription vocale).
    language : str
        Code de langue cible : "fr" (français), "ar" (arabe), "da" (darija).
    sensor_data : dict, optionnel
        Lectures actuelles du capteur 4-en-1 RS485, ex. :
        {"pH": 6.5, "humidity": 42, "temperature": 28, "salinity": 1.2}
    ml_prediction : str, optionnel
        Recommandation de culture déjà calculée localement
        (ex. "Olivier" ou "Blé dur").
    selected_zone : str, optionnel
        Zone du champ sélectionnée par l'agriculteur (ex. "B2").
    selected_crop : str, optionnel
        Culture cible choisie par l'agriculteur (ex. "Tomate").
    robot_state : dict, optionnel
        État de mission du robot (point actif, progression).

    Retourne
    --------
    str
        Réponse concise et experte dans la langue demandée.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY manquante. Renseignez-la dans le fichier .env "
            "(clé gratuite : https://aistudio.google.com/apikey)."
        )

    # Garde-fous d'entrée : on borne le message et on ne garde que les derniers
    # tours d'historique (défense en profondeur côté serveur).
    message = (message or "").strip()[:_MAX_MESSAGE_CHARS]
    if not message:
        raise RuntimeError("Message vide : rien à envoyer au LLM.")
    history = (history or [])[-_MAX_HISTORY_TURNS:]

    system_prompt = _build_system_prompt(
        language=language,
        sensor_data=sensor_data,
        ml_prediction=ml_prediction,
        selected_zone=selected_zone,
        selected_crop=selected_crop,
        robot_state=robot_state,
        correction_context=correction_context,
    )

    # Format de l'API Generative Language : le prompt système passe par
    # `system_instruction`, l'échange par `contents`. On reconstruit l'historique
    # multi-tours pour une vraie conversation (l'agriculteur peut enchaîner les
    # questions de suivi). Rôles Gemini : "user" et "model".
    contents = []
    for turn in (history or []):
        if not isinstance(turn, dict):
            continue
        text = (turn.get("content") or turn.get("text") or "").strip()
        if not text:
            continue
        role = turn.get("role", "user")
        gem_role = "model" if role in ("bot", "model", "assistant") else "user"
        contents.append({"role": gem_role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.4,
            # Assez large pour des explications détaillées complètes (sans coupure
            # en milieu de phrase) quand l'agriculteur en demande, sans être illimité
            # (coût/latence). Réponses courtes par défaut.
            "maxOutputTokens": 1100,
            # Désactive le mode "thinking" des modèles Gemini 2.5 : pour une
            # réponse courte, le raisonnement interne consommerait tout le
            # budget de tokens (réponse tronquée / vide) et ajoute de la latence.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    # Liste ordonnée des modèles à tenter : le modèle principal, puis le repli
    # léger si le principal sature son quota (HTTP 429). On évite le doublon si
    # le repli est vide ou identique au principal.
    models_to_try = [GEMINI_MODEL]
    if GEMINI_FALLBACK_MODEL and GEMINI_FALLBACK_MODEL != GEMINI_MODEL:
        models_to_try.append(GEMINI_FALLBACK_MODEL)

    async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
        last_error: Optional[RuntimeError] = None
        for idx, model in enumerate(models_to_try):
            is_last = idx == len(models_to_try) - 1
            try:
                return await _call_gemini(client, model, payload)
            except _QuotaError as err:
                # Quota épuisé : on passe au modèle de repli s'il en reste un.
                last_error = RuntimeError(str(err))
                if is_last:
                    raise last_error from err
                # sinon : on tente le modèle suivant (boucle)
    # Inatteignable en pratique (la boucle retourne ou relève), garde-fou.
    raise last_error or RuntimeError("Échec de l'appel au LLM Gemini.")


class _QuotaError(RuntimeError):
    """Erreur de quota Gemini (HTTP 429) — déclenche le repli vers le modèle léger."""


async def _call_gemini(client: httpx.AsyncClient, model: str, payload: dict) -> str:
    """Effectue un appel generateContent pour un modèle donné et renvoie le texte.

    Lève `_QuotaError` sur HTTP 429 (pour permettre le repli) et `RuntimeError`
    sur toute autre erreur HTTP, réseau, ou réponse vide.
    """
    url = f"{GEMINI_BASE_URL}/models/{model}:generateContent"
    try:
        response = await client.post(
            url,
            params={"key": GEMINI_API_KEY},
            json=payload,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as err:
        # Inclure le status + un extrait du corps : 429 (quota free-tier,
        # fréquent sur les modèles 2.0) et 400 (modèle/clé invalides) doivent
        # rester diagnosticables (cf. revue de code, finding #4).
        body = (err.response.text or "")[:300]
        detail = (
            f"Échec de l'appel au LLM Gemini (HTTP {err.response.status_code}, "
            f"modèle={model}). Détail : {body}"
        )
        if err.response.status_code == 429:
            raise _QuotaError(detail) from err
        raise RuntimeError(detail) from err
    except httpx.HTTPError as err:
        raise RuntimeError(
            f"Échec de l'appel au LLM Gemini ({url}, modèle={model}). "
            "Vérifiez votre connexion internet et la validité de GEMINI_API_KEY."
        ) from err

    data = response.json()
    # Réponse Gemini : candidates[0].content.parts[*].text
    candidates = data.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts") if candidates else []
    text = "".join(p.get("text", "") for p in (parts or [])).strip()
    if not text:
        # Réponse 200 mais vide : blocage de sécurité, finishReason=MAX_TOKENS,
        # promptFeedback bloqué… On lève une erreur explicite plutôt que de
        # renvoyer "" silencieusement (cf. revue de code, finding #5). Le
        # frontend bascule alors sur localAnswer().
        reason = ""
        if candidates:
            reason = candidates[0].get("finishReason", "")
        feedback = (data.get("promptFeedback") or {}).get("blockReason", "")
        raise RuntimeError(
            "Réponse Gemini vide "
            f"(finishReason={reason or 'n/a'}, blockReason={feedback or 'n/a'})."
        )
    return text


# ---------------------------------------------------------------------------
# Synthèse vocale (TTS) Gemini
# ---------------------------------------------------------------------------

def _pcm_to_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    """Emballe du PCM brut 16 bits mono dans un conteneur WAV lisible par le
    navigateur (l'API Gemini renvoie du L16/PCM sans en-tête)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # 16 bits
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


async def synthesize_speech(text: str, language: str = "ar") -> bytes:
    """Génère l'audio (WAV 24 kHz mono) d'un texte via le modèle TTS de Gemini.

    La voix prédéfinie (`GEMINI_TTS_VOICE`) parle automatiquement la langue du
    texte — on obtient donc une vraie voix arabe naturelle, sans dépendre des
    voix TTS locales du navigateur. Lève `RuntimeError` en cas d'échec (le
    frontend bascule alors sur la voix locale ou affiche un message).
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY manquante. Renseignez-la dans le fichier .env "
            "(clé gratuite : https://aistudio.google.com/apikey)."
        )

    clean = (text or "").strip()
    if not clean:
        raise RuntimeError("Texte vide : rien à synthétiser.")

    payload = {
        "contents": [{"parts": [{"text": clean}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": GEMINI_TTS_VOICE}
                }
            },
        },
    }

    url = f"{GEMINI_BASE_URL}/models/{GEMINI_TTS_MODEL}:generateContent"
    async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
        try:
            response = await client.post(
                url, params={"key": GEMINI_API_KEY}, json=payload
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as err:
            body = (err.response.text or "")[:300]
            raise RuntimeError(
                f"Échec TTS Gemini (HTTP {err.response.status_code}, "
                f"modèle={GEMINI_TTS_MODEL}). Détail : {body}"
            ) from err
        except httpx.HTTPError as err:
            raise RuntimeError(
                f"Échec TTS Gemini ({url}, modèle={GEMINI_TTS_MODEL}). "
                "Vérifiez votre connexion internet et la validité de GEMINI_API_KEY."
            ) from err

    data = response.json()
    candidates = data.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts") if candidates else []
    inline = None
    mime = ""
    for p in (parts or []):
        # camelCase (inlineData) côté v1beta ; on tolère snake_case par prudence.
        blob = p.get("inlineData") or p.get("inline_data")
        if blob and blob.get("data"):
            inline = blob["data"]
            mime = blob.get("mimeType") or blob.get("mime_type") or ""
            break
    if not inline:
        reason = candidates[0].get("finishReason", "") if candidates else ""
        raise RuntimeError(f"Réponse TTS Gemini sans audio (finishReason={reason or 'n/a'}).")

    pcm = base64.b64decode(inline)
    # mimeType typique : "audio/L16;codec=pcm;rate=24000" → on en extrait le débit.
    m = re.search(r"rate=(\d+)", mime)
    sample_rate = int(m.group(1)) if m else 24000
    return _pcm_to_wav(pcm, sample_rate)
