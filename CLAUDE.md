# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Vue d'ensemble

**Agribotics** est un prototype académique réel de robot agricole mobile basé sur une **Raspberry Pi** (châssis **Adeept Pi Car Pro**). Le robot navigue sur des points prédéfinis d'une parcelle, acquiert des mesures de sol et génère des recommandations agronomiques multilingues (FR / AR / Darija marocaine).

**Acquisition du sol (4 variables) :** la **température (DS18B20)** et l'**humidité (capteur capacitif)** sont lues en réel sur un **ESP32 relié en USB série**. Le **pH** et l'**EC** sont **générés de façon agronomiquement cohérente à partir** de ces deux valeurs réelles (`SoilSynthesizer`). **Plus aucun capteur RS485.**

**Le code actif est à la racine du dépôt** dans les dossiers `backend/`, `ml_model/`, `raspberry_pi/` et `frontend/`. Aucun sous-dossier de projet supplémentaire — toutes les commandes s'exécutent depuis la racine.

L'**inférence agronomique (ML + règles) est 100 % locale** — aucun service cloud requis pour le cœur métier. **Seule la couche conversationnelle (chatbot) utilise le cloud** : le LLM est **Gemini** via l'API **Google AI Studio** (clé `GEMINI_API_KEY`, connexion internet requise pour le chat uniquement).

---

## Commandes

Toutes les commandes s'exécutent depuis **la racine du dépôt**.

### Installation (première fois)
```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

`pyserial` (lecture de l'ESP32 capteurs + sonde NEMA en USB série) est dans les dépendances. Sur PC/Mac de dev, l'absence d'ESP32 fait basculer automatiquement en mode `mock` (simulation).

### Gemini (LLM chatbot, cloud Google AI Studio) — préparation
1. Obtenir une clé API gratuite : https://aistudio.google.com/apikey
2. La renseigner dans `.env` : `GEMINI_API_KEY=...`

Aucun téléchargement de modèle ni RAM consommée localement (contrairement à
l'ancien Ollama/Qwen). Le modèle est choisi via `.env` (`GEMINI_MODEL`, défaut
`gemini-2.5-flash`) — **aucun changement de code requis** entre machines. NB : les modèles `2.0` peuvent avoir un free tier à 0 selon le compte/la région (HTTP 429) ; les `2.5` disposent du quota gratuit.

### Backend FastAPI
```bash
./.venv/bin/python -m uvicorn backend.app:app --reload
# API : http://localhost:8000 — docs interactives : /docs
```

### Frontend
```bash
# Version simulation (données statiques, aucun backend requis) — port 5501
cd frontend/frontend_simulation && python3 -m http.server 5501

# Version backend réel (consomme l'API FastAPI) — port 5500
cd frontend/frontend_real_backend && python3 -m http.server 5500
```

Chaque frontend contient un `index.html` qui redirige vers `agribotics_v5.html` :
ouvrir directement `http://localhost:5500/` (ou `:5501/`) lance l'app, au lieu
d'afficher le listing du dossier.

### Raspberry Pi / robot (mock sur PC ou hardware sur Pi)
```bash
# Mission complète 3×3 (alimente le backend en 9 mesures)
APP_MODE=mock ./.venv/bin/python -m raspberry_pi.main

# Un seul point
APP_MODE=mock ./.venv/bin/python -m raspberry_pi.main --point B2

# Sur le robot réel : APP_MODE=hardware
APP_MODE=hardware python3 -m raspberry_pi.main

# Essai complet en simulation (SENSOR_MODE=mock) : robot + bras réels, mesures simulées
# (stabilisation + collecte en temps réel ; valeurs aberrantes injectées sur
# ~25 % des points pour tester alertes salinité / qualité "suspect")
APP_MODE=hardware SENSOR_MODE=mock SENSOR_MOCK_OUTLIER_RATE=0.25 \
  python3 -m raspberry_pi.main --watch

# Test matériel sûr (moteurs / servo) — robot sur support, vitesse faible
APP_MODE=hardware python3 -m raspberry_pi.hardware_test --test all
```

### Démarrer toute la chaîne en une commande
```bash
./start_demo.sh                     # PC, mode mock (backend + robot --watch + frontend :5500)
APP_MODE=hardware ./start_demo.sh    # Raspberry Pi, robot réel
```

### Lancer les tests
```bash
./.venv/bin/python -m unittest discover -s tests -q
```

### Entraîner le modèle ML
```bash
./.venv/bin/python ml_model/train.py
# 1) (re)génère ml_model/data/final_dataset.csv (10 000 lignes, 10 classes équilibrées)
# 2) entraîne RF / SVC / GB / LogReg avec StratifiedKFold k=5
# 3) sélectionne le meilleur par F1-macro
# 4) produit ml_model/best_model.pkl + ml_model/scaler.pkl
#
# Tant que ces fichiers sont absents, l'API utilise le moteur de règles
# (engine: "rules") comme fallback automatique. Aucune exception levée.
# Pour repasser sur les règles : rm ml_model/best_model.pkl ml_model/scaler.pkl
```

### Régénérer uniquement le dataset (sans entraînement)
```bash
./.venv/bin/python ml_model/data_preparation.py
# Par défaut 10 000 lignes (1000/culture). Surcharge :
# ./.venv/bin/python ml_model/data_preparation.py -n 5000
```

---

## Variables d'environnement

Copier `backend/.env.example` → `.env` à la racine du projet.

| Variable | Défaut | Rôle |
|---|---|---|
| `APP_MODE` | `mock` | `mock` = dev/démo sans matériel · `hardware` = robot réel |
| `SENSOR_MODE` | `auto` | `auto` = suit `APP_MODE` · `mock` = force la simulation même en hardware (ignore l'ESP32) · `hardware` = capteur réel (ESP32 + synthèse pH/EC ; repli mock si ESP32 absent) |
| `SENSOR_MOCK_OUTLIER_RATE` | `0` | Probabilité [0..1] qu'un point mock produise des valeurs aberrantes (salinité, pH acide, sol sec, temp « suspect ») |
| `SENSOR_MOCK_OUTLIER_POINTS` | _(vide)_ | Labels forcés en aberrant, ex. `B2,C1` |
| `GEMINI_API_KEY` | _(vide)_ | Clé API Google AI Studio (obligatoire pour le chatbot) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Modèle Gemini servi (2.5-flash / 2.5-flash-lite) |
| `GEMINI_FALLBACK_MODEL` | `gemini-2.5-flash-lite` | Modèle de repli si le principal renvoie 429 (quota) ; vide = désactivé |
| `GEMINI_TTS_MODEL` | `gemini-2.5-flash-preview-tts` | Modèle TTS Gemini pour la route `/api/tts` (vraie voix arabe) |
| `GEMINI_TTS_VOICE` | `Kore` | Voix prédéfinie Gemini (parle la langue du texte) |
| `TTS_PROVIDER` | _(suit `LLM_PROVIDER`)_ | Fournisseur VOIX découplé du chat (`gemini`/`openai`) — hybride possible |
| `STT_PROVIDER` | _(suit `LLM_PROVIDER`)_ | Fournisseur TRANSCRIPTION micro→texte (`gemini`/`openai`) — `openai` (Whisper) recommandé en arabe/darija |
| `OPENAI_STT_MODEL` | `gpt-4o-transcribe` | Modèle STT OpenAI pour `/api/stt` (ou `whisper-1`) |
| `GEMINI_STT_MODEL` | `gemini-2.5-flash` | Modèle STT Gemini pour `/api/stt` (n'accepte pas le webm de Chrome) |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` | Endpoint Generative Language API |
| `GEMINI_TIMEOUT` | `60` | Timeout HTTP de l'appel Gemini (s) |
| `ESP32_SENSOR_PORT` | _(vide)_ | Si défini (+ mode hardware) : **température (DS18B20) + humidité (capteur capacitif)** lues depuis un **ESP32 en USB série**. Le **pH + EC** sont alors **synthétisés à partir** de ces valeurs réelles (`SoilSynthesizer`). Préférer un chemin stable `/dev/serial/by-id/...`. Vide ou ESP32 absent → repli simulation (mock) |
| `ESP32_SENSOR_BAUD` / `ESP32_SENSOR_WARMUP_S` | `115200` / `6` | Débit série ESP32 + attente max (s) de la 1ʳᵉ trame au démarrage. Le port est ouvert **DTR/RTS au repos** (sinon reset de l'ESP32 → on ne capte que le boot ROM à 74880 baud) |
| `ESP32_SENSOR_STALE_S` | `8` | Au-delà de N secondes sans trame **fraîche** (temp **et** humidité), l'acquisition est jugée en panne (ESP32 débranché/muet, ou DS18B20 en « Erreur ») → **repli automatique en simulation (mock)** à chaque lecture, et **reprise** dès que l'ESP32 réémet. L'ESP32 émet ~toutes les 2 s |
| `SENSOR_MOCK_PROFILE` | `None` | En mock, force le profil d'une zone (`A1`..`C3`) |
| `AGRIBOTICS_API_BASE` | `http://127.0.0.1:8000` | URL du backend pour `raspberry_pi/main.py` |
| `AGRIBOTICS_DB_PATH` | `.agribotics/state.sqlite3` | SQLite backend : plan de mission + mesures persistées |
| `AGRIBOTICS_ROBOT_OUTBOX` | `.agribotics/robot_outbox.jsonl` | File d'attente disque du robot : mesures non transmises (résilience réseau), retransmises auto |
| `CORS_ORIGINS` | `*` | Origines CORS autorisées par la FastAPI |
| `WEATHER_LAT` | `33.9` | Latitude pour la météo Open-Meteo (défaut : plaine du Saïss, Maroc) |
| `WEATHER_LON` | `-5.55` | Longitude pour la météo Open-Meteo |
| `WEATHER_TIMEOUT` | `8` | Timeout HTTP de l'appel Open-Meteo (s) |
| `USE_EMBEDDED_MODEL` | `0` | `1` = active le modèle ML embarqué expérimental (recherche ; sinon modèle de production) |
| `PCA9685_ADDRESS` | `0x5f` | Adresse I2C du PCA9685 (robot réel) |
| `MOTOR_LEFT_IN1/IN2`, `MOTOR_RIGHT_IN1/IN2` | `15/14`, `12/13` | Canaux PCA des 2 moteurs DC |
| `STEER_SERVO_CHANNEL` / `STEER_*_DEG` | `0` / `85,0,180` | Servo de direction : canal + angles centre/gauche/droite (validés robot) |
| `DRIVE_THROTTLE` | `-0.15` | Throttle SIGNÉ ligne droite (avant = négatif sur ce câblage, validé) |
| `DRIVE_RAMP_S` | `0.5` | **Démarrage en douceur (anti-brownout)** : monte le throttle de 0 à la consigne sur N s au lieu d'un échelon brutal → lisse l'appel de courant d'inrush des moteurs qui fait chuter la batterie et peut couper la Pi/le backend au démarrage de la mission. `0` = échelon (ancien comportement) |
| `DRIVE_KICK` | `0` | **Coup de reins de démarrage** (magnitude, même signe que la marche) : la rampe `DRIVE_RAMP_S` part de `±DRIVE_KICK` au lieu de 0, c.-à-d. **juste au-dessus du seuil de démarrage (stiction) des moteurs**. Sans lui, pendant la portion `0→seuil` de la rampe les 2 moteurs ne s'arrachent pas en même temps (frottements différents) → **le robot dévie au tout début de chaque ligne droite**. En partant au-dessus du seuil, les 2 roues démarrent ENSEMBLE (plus de déviation de départ) tout en gardant l'anti-brownout. Régler juste sous la consigne `DRIVE_THROTTLE` (ex. `0.12`–`0.18` pour une consigne `-0.25`). Borné à `|DRIVE_THROTTLE|`. `0` = rampe depuis 0 (ancien comportement) |
| `TURN_THROTTLE` | `0.18` | Throttle pendant les virages en arc |
| `TURN_90_S` | `1.2` | Durée d'un quart de tour en arc (~90°) |
| `PIVOT_TRIM_RIGHT` / `PIVOT_TRIM_LEFT` | `0` / `0` | Compensation de TRANSLATION du pivot, PAR SENS (composante commune aux 2 roues → annule la dérive sans changer la rotation). `+` = pousse vers l'arrière (corrige un robot qui avance pendant le pivot), `−` = corrige un recul. À régler au sol pour un pivot « sur place » net |
| `POST_TURN_RIGHT_BACKUP_M` / `POST_TURN_LEFT_BACKUP_M` | `0` / `0` | Recul de compensation APRÈS une rotation (m PHYSIQUES, par sens) : raccourcit d'autant la ligne droite qui suit (résidu reculé en fin si pas de segment). ×2 pour un demi-tour. Corrige l'avance résiduelle d'un pivot que `PIVOT_TRIM_*` n'absorbe pas |
| `ROBOT_SPEED_MPS` | `0.19` | Vitesse ligne droite (≈35-40 cm en 2 s, validé) |
| `ROBOT_WORLD_SCALE` | `1.0` | Échelle plan→physique : démo 1 m × 1 m avec grille 6 m → `0.15`. N'affecte ni l'UI ni les mesures |
| `ROBOT_MAX_FIELD_M` | `0.9` | Côté max (m) du carré que le parcours PHYSIQUE ne dépasse jamais : le robot abaisse auto l'échelle si le plan édité est trop grand (jamais l'inverse). `0.9` → ≤ 0,81 m² (marge sous 1 m²). N'affecte ni l'UI ni les mesures |
| `ROBOT_RETURN_HOME` | `0` | `1` = retour à (0,0) en fin de mission (jamais après arrêt d'urgence). Les demi-tours du retour se font par la GAUCHE (`prefer_left_turns`, évite le résidu d'avance des rotations droites) |
| `OBSTACLE_AVOIDANCE` / `OBSTACLE_MIN_DISTANCE_CM` / `OBSTACLE_TIMEOUT_S` | `1` / `12` / `20` | Ultrason anti-obstacle (trigger 23 / écho 24) : pause + reprise auto, abandon propre au timeout |
| `SIGNALS_ENABLED` / `LED_PINS` / `BUZZER_PIN` | `1` / `25,11` / `18` | LEDs + buzzer (bips mission, clignotement par point, alerte obstacle) — no-op si absents |
| `PROBE_SERVO_CHANNEL` | _(vide)_ | Canal de l'ÉPAULE du bras-sonde (validé : `2`) ; vide = descente simulée |
| `PROBE_ANGLE_UP/DOWN` / `PROBE_ARM_HOME` | `90/150` / `1:90,3:140,4:80` | Angles épaule haut/bas + posture home des autres servos du bras |
| `PROBE_SERIAL_PORT` | _(vide)_ | Si défini (+ hardware) : sonde NEMA pilotée par un **ESP32 en USB série**. Préférer un chemin stable `/dev/serial/by-id/...` |
| `PROBE_SERIAL_BAUD` / `PROBE_SERIAL_TIMEOUT` | `115200` / `15` | Débit série ESP32 + attente max de l'accusé `OK` (s) = borne de la course de la sonde |
| `PROBE_NEMA_GPIO` | `0` | `1` (+ hardware) : sonde NEMA pilotée **DIRECTEMENT par les GPIO de la Pi** (driver A4988/DRV8825 STEP/DIR, sans ESP32). **Priorité la plus haute** dans `build_probe()`. Mouvement temporisé avec rampe accél./décél. |
| `PROBE_NEMA_STEP_PIN` / `PROBE_NEMA_DIR_PIN` | `26` / `27` | Broches BCM STEP/DIR (phys. 37 / 13). Masse commune Pi↔driver↔alim, RESET+SLEEP au 3,3 V Pi, EN à GND |
| `PROBE_NEMA_RPM` / `PROBE_NEMA_START_RPM` / `PROBE_NEMA_ACCEL_S` | `150` / `50` / `1.2` | Vitesse de croisière, vitesse de démarrage (sous le couple de décrochage) et durée des rampes (s). La rampe évite le décrochage du pas-à-pas |
| `PROBE_NEMA_DOWN_S` / `PROBE_NEMA_UP_S` | `9` / `=DOWN_S` | Durées (s) de descente / remontée complètes (calibrées au champ) |
| `PROBE_NEMA_DOWN_DIR` / `PROBE_NEMA_UP_DIR` | `L` / `H` | Sens validés sur le robot : DESCENTE = `L` (LOW), REMONTÉE = `H` (HIGH) |
| `PROBE_NEMA_STEPS_PER_REV` | `200` | Pas par tour du moteur (NEMA 17 = 200) |

---

## Arborescence réelle

```
PLBD/
├── backend/                            # API FastAPI 100 % locale
│   ├── app.py                          # Routes : /health, /api/status, chat, tts, mission, measurements, recommendation
│   ├── chatbot_llm.py                  # Client LLM async (httpx) : chat + TTS (voix) + STT (micro→texte), providers Gemini/OpenAI
│   ├── state.py                        # APP_STATE singleton (RobotState + Measurement + history)
│   ├── persistence.py                  # Persistance SQLite (plan de mission + mesures)
│   ├── weather_service.py              # Bulletin Open-Meteo + consigne d'irrigation
│   ├── .env.example
│   └── __init__.py
│
├── ml_model/                           # Inférence + règles agronomiques + pipeline ML
│   ├── predict.py                      # predict_top_crops() — ML si dispo, sinon rules
│   ├── rules/
│   │   ├── crop_catalog.py             # 10 cultures × 4 plages (pH, humidité, temp, EC)
│   │   ├── engine.py                   # Score pondéré + top_k + salinity_alert
│   │   └── correction.py               # Diagnostic sol → corrections pour une culture cible
│   ├── inference/__init__.py           # Shim de compatibilité
│   ├── data_loader.py                  # Générateur synthétique 10 000 lignes (cf. crop_catalog)
│   ├── data_preparation.py             # (Re)génère final_dataset.csv ; vérifie périmètre 4 vars
│   ├── preprocess.py                   # StandardScaler + split stratifié ; ordre features fixe
│   ├── train.py                        # RF/SVC/GB/LogReg + CV 5-fold + sélection F1-macro
│   ├── dataset_analysis.py             # (héritage)
│   ├── best_model.pkl                  # Modèle sélectionné (Gradient Boosting par défaut)
│   ├── scaler.pkl                      # StandardScaler ajusté sur le train set
│   └── data/
│       └── final_dataset.csv           # 10 000 lignes synthétiques, 10 classes équilibrées
│
├── raspberry_pi/                       # Robot + acquisition
│   ├── main.py                         # Orchestrateur mission (déplacement+sonde+mesure+abort)
│   ├── hardware_test.py                # Test matériel sûr (moteurs / servo)
│   ├── acquisition_manager.py          # Stabilisation 4 s + 10 lectures + stats
│   ├── robot/                          # Couche robot/sonde isolée
│   │   ├── base.py                     # Interfaces RobotController / ProbeController
│   │   ├── mock_controller.py          # Implémentations simulées (PC / repli)
│   │   ├── adeept_controller.py        # Pilotage réel PiCar-Pro (PCA9685 : moteurs + servo)
│   │   ├── esp32_probe.py              # Sonde NEMA pilotée par un ESP32 en USB série (DOWN/UP + accusé OK)
│   │   ├── nema_probe.py               # Sonde NEMA pilotée DIRECTEMENT par les GPIO de la Pi (STEP/DIR + rampe)
│   │   └── __init__.py                 # build_robot() / build_probe() selon APP_MODE
│   ├── offline_buffer.py               # File hors-ligne des mesures (résilience réseau)
│   └── sensors/
│       ├── soil_sensor.py              # Capteur de sol unifié : ESP32 (temp/hum réels) + SoilSynthesizer (pH/EC) ou mock
│       └── esp32_sensor.py             # Lecteur série température (DS18B20) + humidité (capacitif) via ESP32 USB
│
├── frontend/
│   ├── frontend_simulation/            # Démo autonome — port 5501
│   │   ├── index.html                  # Redirection → agribotics_v5.html
│   │   ├── agribotics_v5.html
│   │   ├── css/style.css
│   │   └── js/ (data_model.js, map.js, app.js, chatbot.js, api.js, i18n.js, ...)
│   └── frontend_real_backend/          # Consomme l'API FastAPI — port 5500
│       ├── index.html                  # Redirection → agribotics_v5.html
│       └── (mêmes fichiers que la version simulation, api.js connecté)
│
├── tests/                              # Suite unittest (ML, backend, chatbot)
├── data/                               # Datasets recherche (pipeline embarqué, hors prod)
├── start_demo.sh                       # Lance backend + robot --watch + frontend
├── MODEL_CARD.md                       # Carte des modèles ML
├── .venv/                              # Environnement Python 3.12+
├── .env                                # Variables d'environnement (à créer)
├── requirements.txt
├── README.md                           # Guide de lancement / démo
└── CLAUDE.md                           # Ce fichier
```

---

## Architecture

### Flux système

```
APP_MODE=hardware (robot) :
  raspberry_pi.main
    → AcquisitionManager.collect(point)
      → _Esp32SoilSensor.read() × 10  (stabilisation 4 s ; temp/hum ESP32 + pH/EC synthétisés)
      → stats mean/median/pstdev
      → MeasurementRecord
    → POST /api/measurements
      → APP_STATE.record_measurement()
      → met à jour RobotState (progress_pct, status=done à 9/9)

APP_MODE=mock (dev/démo) :
  même flux, mais _MockSensor produit des lectures cohérentes : profils curés
  A1..C3, ou champ déterministe soil_at(x,y) pour les points arbitraires du plan.

UI :
  frontend_real_backend appelle GET /api/mission, /api/measurements,
  /api/recommendation. Le chatbot appelle POST /api/chat.
```

### Backend (`backend/`)

- **`app.py`** — Application FastAPI mono-fichier. Enregistre toutes les routes et le middleware CORS. Importe les helpers via `from .chatbot_llm`, `from .state` et `from ml_model.predict` (les packages `backend/` et `ml_model/` sont frères à la racine).
- **`state.py`** — Singleton `APP_STATE` (dataclasses) : `RobotState` (status, active_point, progress_pct), **`plan` (liste de `MissionPoint{label, x, y}`)**, `command` (`idle | requested | running | done`), dict `measurements_by_zone`, liste `history`. Le **plan de mission est dynamique** : l'interface le redéfinit (`POST /api/mission/plan`), `total_points` et la validation des mesures (`has_point`) en découlent. La grille 3×3 historique (A1..C3) n'est plus qu'un **plan par défaut** (amorçage + démo). Le plan de mission et les mesures sont persistés dans SQLite (`AGRIBOTICS_DB_PATH`) et rechargés au redémarrage ; la commande robot reste volatile. `RobotState.status` peut valoir `idle | requested | moving | measuring | done | emergency_stop`.
- **`persistence.py`** — Couche SQLite minimale (sqlite3 stdlib) : `replace_plan`, `save_measurement`, `clear_measurements`, `load_plan`, `load_measurements`. Les erreurs SQLite sont absorbées (`_safe_persist`) pour que le backend reste utilisable en mémoire.
- **`weather_service.py`** — Bulletin Open-Meteo (sans clé) + consigne d'irrigation (route `/api/weather`).
- **`chatbot_llm.py`** — Client **Gemini** (Google AI Studio, cloud) async (httpx), endpoints `generateContent` (chat) et TTS. Le prompt système passe par `system_instruction`, l'échange (historique multi-tours borné) par `contents`. Assistant **conversationnel** : il comprend tout message, explique en détail à la demande (« pourquoi / comment »), et réoriente poliment si hors-sujet. Garde-fous du prompt :
  - 4 variables capteur uniquement (pH, humidité, température, EC)
  - **N/P/K** : ne jamais prétendre les avoir mesurés ni recommander d'engrais NPK (une évocation pédagogique du rôle d'un nutriment reste tolérée)
  - recommandations de culture limitées aux 10 cultures cibles
  - langue forcée selon `language` (`fr` / `ar` / `da`)
  - **diagnostic de correction injecté** (`correction_context`) : pour tout ce qui touche CE sol, le LLM s'appuie strictement sur `rules.correction.diagnose()` (4 variables) — il n'invente aucun chiffre
  - **bulletin météo injecté** (`weather_context`) : pour les questions d'irrigation/pluie, le LLM s'appuie strictement sur `weather_service.get_forecast()` (Open-Meteo, déterministe) — il n'invente jamais de prévision. Le contexte est construit par `_build_weather_context()` dans `app.py` (cache mémoire : 30 min si dispo, 2 min sinon, pour ne pas appeler Open-Meteo à chaque message)
  - garde-fous d'entrée : message borné (2000 car.), historique borné (8 tours), modèle de repli automatique sur quota 429.
- **`__init__.py`** — Marque `backend/` comme package Python.

### Routes API

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/` | Healthcheck + config Gemini courante |
| GET | `/health` | Healthcheck minimal `{status, service}` (supervision / démo) |
| GET | `/api/status` | État consolidé : mission, mode, dernière mesure + recommandation, LLM |
| GET | `/api/weather` | Bulletin 3 j (Open-Meteo, sans clé) + consigne d'irrigation (pluie → reportée/réduite) |
| POST | `/api/chat` | Question agriculteur → réponse LLM contextualisée |
| POST | `/api/tts` | Texte → audio WAV (TTS Gemini cloud) ; vraie voix arabe, repli voix locale si échec |
| POST | `/api/stt` | Audio micro (multipart) → texte (STT cloud Whisper/Gemini) ; bien meilleur que le navigateur en arabe/darija, repli reconnaissance locale si échec |
| GET | `/api/mission` | État robot + progression + `plan` + `command` |
| GET | `/api/mission/plan` | Plan de mission courant (liste de points `{label, x, y}`) — lu par le robot |
| POST | `/api/mission/plan` | Définit le plan de mission depuis l'interface (N points x/y) |
| POST | `/api/mission/start` | Commande le démarrage (`command="requested"`) — le robot `--watch` exécute |
| POST | `/api/mission/end` | Demande l'arrêt (abort) de la mission |
| POST | `/api/mission/stop` | **Arrêt d'urgence** : `command=idle` + `emergency_stop` ; le robot `--watch` stoppe entre 2 points |
| POST | `/api/mission/pause` | **Pause momentanée** : `command=paused` ; le robot s'immobilise sur place entre 2 points et attend (progression conservée) |
| POST | `/api/mission/resume` | **Reprise** après pause : `command=running` ; la mission continue depuis le point en attente |
| POST | `/api/mission/suspend` | **Arrêt → état initial** : `reset()` (en attente, progression 0) ; le robot abandonne entre 2 points et reste PHYSIQUEMENT en place (pas de retour au départ) |
| POST | `/api/mission/reset` | Vide l'état mémoire (conserve le plan) |
| GET | `/api/measurements` | `latest` + `history` + `by_zone` |
| POST | `/api/measurements` | Push d'une mesure (depuis robot ou démo) |
| GET | `/api/recommendation` | Top-k cultures pour toutes zones mesurées |
| GET | `/api/recommendation/{point}` | Top-k cultures pour une zone |
| GET | `/api/recommendation/{point}/explain` | Classement règles 10 cultures + détail par variable (+ `ml_top` si modèle dispo) |
| GET | `/api/recommendation/{point}/correction?crop=X` | Diagnostic du sol pour une culture cible + corrections + cultures mieux adaptées |

### Capteur de sol — ESP32 + synthèse (`raspberry_pi/sensors/`)

- **`soil_sensor.py`** — `build_sensor()` retourne automatiquement :
  - `_Esp32SoilSensor` si le mode résolu est `hardware` ET `ESP32_SENSOR_PORT` est défini : **température + humidité réelles** de l'ESP32, **pH + EC synthétisés** à partir d'elles via `SoilSynthesizer` (repli mock au démarrage si l'ESP32 est absent / pyserial manquant). **Repli automatique RUNTIME** : si pendant la mission l'ESP32 tombe en panne (débranché, muet, trames obsolètes au-delà de `ESP32_SENSOR_STALE_S`, ou DS18B20 en « Erreur » → `Esp32Sensor.is_fresh()` faux), **chaque lecture bascule sur le mock** (`fallback`) et **reprend** le réel dès que l'ESP32 réémet — la mission ne se fige jamais
  - `_MockSensor` sinon. Priorité aux profils curés A1..C3 (démo) ; pour tout autre point, **`soil_at(x, y)`** — champ de sol synthétique déterministe et spatialement cohérent (miroir exact de `soilAt()` dans `js/data_model.js`). `set_location(label, x, y)` positionne le mock.

  Le mode capteur est **découplé du mode robot** : `SENSOR_MODE` (`auto`/`mock`/`hardware`, défaut `auto` = suit `APP_MODE`). `APP_MODE=hardware SENSOR_MODE=mock` = mode « essai complet en simulation » (robot et bras réels, mesures simulées en temps réel, ESP32 ignoré). Le mock peut **injecter des profils aberrants** (`SENSOR_MOCK_OUTLIER_RATE` probabiliste et/ou `SENSOR_MOCK_OUTLIER_POINTS` forcés) : `saline` (EC 7.2 → alerte salinité), `acide` (pH 3.5), `sec` (humidité 4 %), `canicule` (57 °C → qualité `suspect`). Les profils restent dans les bornes acceptées par le backend (pas de 422) pour exercer les garde-fous **en aval**.

  **`SoilSynthesizer`** — génère pH + EC de façon **agronomiquement cohérente à partir de l'humidité + température RÉELLES** : EC ↑ avec l'humidité (l'eau conduit) et avec la température (≈ +1,9 %/°C autour de 25 °C), pH légèrement plus acide en sol humide. Petit bruit capteur + dérive lente bornée (marche aléatoire lissée) → rendu « temps réel » crédible, valeurs successives proches (qualité `good`). Bornes : pH ∈ [5.3, 7.9], EC ∈ [0.15, 4.5] mS/cm.
- **`esp32_sensor.py` — lecteur série ESP32 (température + humidité réelles)** : un **ESP32 en USB série** (DS18B20 1-Wire + capteur d'humidité capacitif sur ADC) émet en clair toutes les ~2 s `Température : XX.X °C, Humidité : YY.Y %` ; un thread de fond maintient la dernière valeur, `latest()` la renvoie sans bloquer. **Piège critique** : le port est ouvert avec **DTR/RTS au repos** (`dtr=False, rts=False`), sinon le CP2102 reset l'ESP32 à chaque ouverture et on ne capte que le boot ROM (74880 baud, illisible à 115200). `parse_line()` est une fonction pure testée (tolère `é`/`Temp`, virgule/point, cas `Erreur` de la DS18B20 déconnectée). Test indépendant : `python3 deploy/esp32_sensor_test.py <port>`.
- **`acquisition_manager.py`** — Protocole `AcquisitionManager.collect(point)` :
  1. (hardware seulement) stabilisation 4 s
  2. 10 lectures espacées de `interval_s` (0.5 s hardware, 0.0 s mock)
  3. statistiques mean/median/pstdev par variable
  4. qualité auto (`good`/`fair`/`noisy`) selon écart-type pH + EC
  5. retourne `MeasurementRecord` prêt pour POST API

### ML (`ml_model/`)

#### Vue d'ensemble du pipeline

```
crop_catalog.py (vérité agronomique : 10 cultures × 4 plages)
    │
    ├──→ rules/engine.py            ── score pondéré déterministe ──┐
    │                                                                │
    └──→ data_loader.py             ── 10 000 lignes synthétiques   │
              │                                                       │
              ▼                                                       │
        data_preparation.py         ── final_dataset.csv             │
              │                                                       │
              ▼                                                       │
        preprocess.py               ── StandardScaler + split 80/20  │
              │                                                       │
              ▼                                                       │
        train.py                    ── 4 modèles + CV 5-fold         │
              │                                                       │
              ▼                                                       │
   best_model.pkl + scaler.pkl                                        │
              │                                                       │
              ▼                                                       ▼
         predict.py  ──── si pkl dispo → engine="ml" ──── sinon engine="rules"
              │
              ▼
   backend/app.py /api/recommendation
```

#### Modules

- **`rules/crop_catalog.py`** — `CropProfile` dataclass figée pour les 10 cultures V1 : Blé, Tomate, Oignon, Carotte, Pomme de terre, Orge, Betterave à sucre, Olivier, Vigne, Pastèque. Plages agronomiques en pH / humidité (%) / température (°C) / EC (mS/cm) + référence compost. **C'est la source de vérité partagée entre le moteur de règles et le générateur ML.**
- **`rules/engine.py`** — Score pondéré [0–100] par variable, puis pondération globale : **pH × 0.30, humidité × 0.30, température × 0.20, EC × 0.20**. `top_k()` retourne les k meilleures cultures. `salinity_alert()` vrai si EC > 2.5 mS/cm.
- **`rules/correction.py`** — Question **inverse** de l'`engine` : « j'ai choisi CETTE culture, comment corriger mon sol ? ». `diagnose(measurement, target_crop)` compare chaque variable à la plage cible (`ok`/`low`/`high`) et renvoie une action concrète déterministe (chaux/dolomie pour relever le pH, soufre pour l'abaisser, irrigation, drainage, lessivage…) + la compatibilité globale + les cultures naturellement mieux adaptées au sol en l'état (`better_suited`). `diagnosis_to_prompt()` sérialise le tout pour le prompt Gemini. **Aucun conseil n'est inventé par le LLM** : il reformule des faits calculés ici.
- **`data_loader.py`** — `generate_dataset(samples_per_crop=1000)` produit un DataFrame de N×10 lignes avec colonnes `[ph, humidity, temperature, ec, label]`. Pour chaque culture : **85 %** au cœur de la plage (bruit σ = width × 0.05), **15 %** en bordure (σ = width × 0.10). Les tirages franchement hors-plage sont désactivés (`out_frac=0.0`) car ils constituaient du bruit d'étiquetage. Clamping physique automatique (pH ∈ [3, 10], EC ∈ [0, 12], …). `FEATURE_ORDER = ["ph", "humidity", "temperature", "ec"]` — **cet ordre est partagé avec preprocess.py et predict.py**.
- **`data_preparation.py`** — Wrapper de `data_loader.generate_dataset()` qui sauvegarde `data/final_dataset.csv` et lève `RuntimeError` si une colonne hors périmètre (N/P/K/rainfall) apparaît. Exécution : `python ml_model/data_preparation.py`.
- **`preprocess.py`** — Charge le CSV, vérifie qu'aucune colonne hors périmètre n'a fuité, split stratifié 80/20 (`random_state=42`), `StandardScaler` ajusté sur le train set seulement et sauvegardé.
- **`train.py`** — Entraîne 4 modèles candidats avec **StratifiedKFold k=5** et score CV `f1_macro`, puis évaluation finale sur le test set (Accuracy, Précision/Rappel pondérés, F1-macro, F1-pondéré). Sélection par F1-macro (tiebreak : F1-pondéré, puis accuracy). Sauvegarde `best_model.pkl` + `scaler.pkl`. Modèles : `RandomForestClassifier(n_estimators=300)`, `SVC(kernel="rbf", C=10, probability=True)`, `GradientBoostingClassifier(n_estimators=200)`, `LogisticRegression(max_iter=2000)`.
- **`predict.py`** — `predict_top_crops(ph, humidity, temperature, ec, k=3)`. Priorité :
  1. **Modèle de production** `best_model.pkl` + `scaler.pkl` (4 features pH/humidité/température/**EC**, 10 cultures FR) → `engine: "ml"`, `model_type: "production"`.
  2. **Modèle embarqué expérimental** `models/embedded_model.pkl` (3 features sans EC, cultures Kaggle tropicales **hors périmètre**) — **désactivé par défaut**, activable via `USE_EMBEDDED_MODEL=1` (recherche / audit uniquement).
  3. Sinon ou erreur de chargement → moteur de règles → `engine: "rules"`.
  - garde-fou agronomique : les propositions ML très incohérentes avec les règles sont pénalisées (score auditable), jamais supprimées silencieusement.
  - retourne `{engine, model_type, top: [{crop, score, details}], alerts, recommendations, explanation}`.
  - mapping sémantique : `ec` (capteur) ↔ `salinity` (alerte) ↔ `ec` (feature ML).
- **`inference/__init__.py`** — Shim de compatibilité : `from ml_model.inference import predict_top_crops` équivaut à l'import direct.

#### Performances actuelles (modèle livré)

Sur 10 000 lignes synthétiques, 10 classes équilibrées :

| Modèle | F1-macro | F1-pondéré | Accuracy (top-1) | **Top-3** | CV F1-macro |
|---|---:|---:|---:|---:|---:|
| **Gradient Boosting** ← retenu | **0.566** | 0.566 | 0.567 | 0.909 | 0.538 ± 0.016 |
| SVC (RBF) | 0.566 | 0.566 | 0.569 | **0.914** | 0.549 ± 0.013 |
| Random Forest | 0.551 | 0.551 | 0.551 | 0.899 | 0.551 ± 0.013 |
| Logistic Regression | 0.452 | 0.452 | 0.457 | 0.827 | 0.448 ± 0.010 |

**Interprétation** : la **métrique de référence est le top-3 (0.91)**, pas le top-1 — parce que l'API expose un top-3, pas une culture unique. Le top-1 (≈ 0.57) est **intrinsèquement plafonné** par les chevauchements agronomiques entre cultures : Carotte/Pomme de terre partagent 92 % de leurs plages, Blé/Orge 84 %. Sur ces paires, une mesure de sol est valide pour les deux cultures à la fois — l'information n'existe pas dans les 4 variables capteur, c'est une borne de Bayes, pas un défaut de modèle. Avec seulement 4 features, le top-3 à 0.91 reste agronomiquement pertinent dans tous les cas testés.

> **Note composition du dataset** : depuis l'itération du 2026-05-28, le générateur tire **85 % cœur / 15 % bordure / 0 % hors-plage** (auparavant 70/20/10). Les 10 % « hors-plage » étaient du bruit d'étiquetage pur (un point poussé dans le cœur d'une autre culture mais gardant l'étiquette d'origine) : les retirer fait passer top-3 de 0.86 → 0.91 et top-1 de 0.49 → 0.57, sans perte de réalisme (la bordure couvre les mesures capteur limites). Cf. `data_loader._sample_in_range`.

#### Pour re-entraîner

```bash
./.venv/bin/python ml_model/train.py
# Régénère data/final_dataset.csv, entraîne les 4 modèles avec CV,
# sélectionne le meilleur, sauvegarde les pickles. ~5 min sur 2 CPU.
```

Pour repasser temporairement sur le moteur de règles : `rm ml_model/best_model.pkl ml_model/scaler.pkl`. Aucune exception levée, l'API bascule automatiquement.

### Frontend (`frontend/`)

Deux versions strictement parallèles :

- **`frontend_simulation/`** (port 5501) : démo autonome, données statiques dans `js/data_model.js`. Aucun backend requis. Profils par zone (A1 alerte salinité, C1 alerte forte, B2 cas typique...).
- **`frontend_real_backend/`** (port 5500) : consomme l'API FastAPI. `js/api.js` fait des `GET /api/mission`, `GET /api/measurements`, et mappe `m.ec ?? m.salinity ?? m.conductivity` vers `data.ec`.

**Carte dynamique & éditeur de plan** : la carte n'est plus une grille figée. Un **éditeur de plan** (injecté en JS au-dessus de la carte mission, dans les deux frontends) permet de définir N points de mesure par coordonnées `{label, x, y}` → **N points = N marqueurs**. `js/data_model.js` expose `currentPlan()`/`planLabels()`, `soilAt(x,y)` (miroir du `soil_at` Python) et `applyPlanPoints()`. Le rendu (`js/map.js`) est une **vue aérienne** : fond photo satellite si `assets/parcelle.jpg` existe (sinon mosaïque agricole procédurale via `drawAerial`), marqueurs ronds dont la taille s'adapte au nombre de points, **distances réelles préservées** (`_layoutField` à échelle uniforme x/y) avec barre d'échelle en mètres. L'éditeur impose une **distance minimale** entre points (`MIN_SPACING_M`). En `real_backend`, l'UI envoie le plan (`POST /api/mission/plan`) puis commande le robot (`startRealMode` → `/start`) ; `syncFromBackend` adopte le plan renvoyé par `GET /api/mission`.

**Variables affichées dans la carte / les jauges** : les 4 du capteur — humidité, pH, température, EC. L'EC est traitée comme variable de première classe (jauge dédiée, couche carte, alerte salinité visuelle).

**Chatbot** (`js/chatbot.js`) : envoie au backend `selected_zone`, `selected_crop`, `zone_data`, `robot_state`. Fonction `localAnswer()` de secours qui produit une réponse FR/AR/Darija déterministe sans LLM si le backend n'est pas joignable. **L'accès se fait via une icône flottante** (FAB bas-droite 🚜, `setupChatLauncher` dans `app.js`) qui ouvre/ferme un panneau — plus de barre de chat permanente. Le panneau (`#chatPanel`) et le FAB sont rattachés à `document.body` (et non à une page) : ils restent donc disponibles depuis **tous les onglets** (Terrain / Carte / Conseils), pas seulement Terrain.

**Libellés boutons mission (real_backend)** : `applyLanguage()` (`js/i18n.js`) relabellise les 3 boutons `.mission-actions` avec les clés **mode réel** `startMission` / `syncBtn` / `stopBtn` (« ▶ Démarrer mission / ↻ Synchroniser / ■ Arrêter »), et non les clés simulation `startSimulation` / `nextStep` / `reset` (ces dernières restent utilisées côté `frontend_simulation`).

**Météo (Open-Meteo)** : `fetchWeather()` (dans `api.js`) remplit `APP_STATE.weather` ; `real_backend` passe par `/api/weather`, `simulation` appelle Open-Meteo en direct (API publique, CORS ok). `recommendActionsForZone` (`data_model.js`) **réduit ou reporte l'irrigation** quand de la pluie est prévue (mêmes seuils que `backend/weather_service.py`), et un bandeau météo l'explique dans le panneau de conseils.

### Raspberry Pi (`raspberry_pi/`)

- **`main.py`** — Orchestrateur de mission piloté par le **plan dynamique**. Source du plan par priorité : `--plan plan.json` → `GET /api/mission/plan` → repli grille 3×3. Argparse : `--point`, `--plan`, `--watch` (**daemon** déclenché par `command=="requested"`), `--no-reset`. **Séquence par point** : `robot.move_to_point` → `probe.lower_probe` → `probe.stabilize` → acquisition capteur → `probe.raise_probe` → push HTTP. **Résilience réseau** : un push raté n'est jamais perdu — la mesure est mise en file sur le disque (`offline_buffer.OfflineBuffer`) et retransmise au début de la mission suivante. **Pilotage temps réel** : en `--watch`, le callback `control` lit `command` du backend AVANT chaque point (`_control_decision`) → `idle/abort` (stop/suspend) stoppe entre deux points, `paused` immobilise le robot sur place et l'endort dans une boucle d'attente (reprise sur `running`/`requested`, jamais sur un hoquet réseau `None`), `running/requested` poursuit ; le robot est toujours arrêté en fin de mission (`finally`).
- **`offline_buffer.py`** — File d'attente disque (JSON Lines) des mesures non transmises au backend. `enqueue()` persiste immédiatement, `flush(push_fn)` retransmet (s'arrête au premier échec pour ne pas marteler le réseau), tolère un fichier corrompu. Garantit **zéro perte de mesure** au champ.
- **`robot/`** — Couche robot/sonde **isolée** (même logique que `sensors.build_sensor`). `base.py` : interfaces `RobotController` / `ProbeController`. `mock_controller.py` : implémentations simulées (PC / repli). `adeept_controller.py` : pilotage **réel** du PiCar-Pro, calqué sur le code mission **validé sur le robot** (`Code_PLBD_23_mission.py`) : PCA9685 `adafruit_motor`, 2 moteurs DC + servo de direction (centre 85°, braquages à fond 0°/180°), **throttles signés** (avant = `-0.15`, virages = `+0.18` — ne pas « corriger » sans réessai), **rotations par défaut = manœuvre en 3 points (`TURN_MODE=kturn`)** : vraie rotation quasi sur place où les roues roulent (pas de raclage) → **le moins de dérapage, adaptée au sable** ; gyroscope pour l'angle exact (90°/180°), repli k-turn chronométré (`KTURN_CYCLES_90`) sans gyro. Modes alternatifs : `pivot` (rotation différentielle sur place) et `arc` (virage en arc, qui fait avancer). Navigation **Manhattan par cap N/E/S/W** (`manhattan_legs()`, fonction pure testée). **`ROBOT_WORLD_SCALE`** rejoue le plan (mètres UI) sur une surface réduite (démo 1 m²) sans toucher UI/backend/mesures. Bras-sonde 4 servos (épaule canal 2 descend, posture home `1:90,3:140,4:80`) — **ou** sonde NEMA pilotée par un ESP32 en USB série (`esp32_probe.py`, `PROBE_SERIAL_PORT`). **Ultrason anti-obstacle** (trigger 23 / écho 24, seuil 12 cm) vérifié toutes les ~0.4 s pendant les lignes droites : pause + LED + bip puis reprise auto quand la voie se dégage, `RuntimeError` propre au timeout (le daemon `--watch` survit). **LEDs/buzzer** (`signals.py`, GPIO 25/11 + 18) : bips mission, clignotement par point — no-op silencieux si gpiozero/broches absents. `__init__.py` : `build_robot()` / `build_probe()` selon `APP_MODE`, avec repli mock si l'I2C échoue. Limite assumée : pas d'odométrie → **dead-reckoning temporisé** (`ROBOT_SPEED_MPS`).
- **`hardware_test.py`** — Test matériel sûr (`--test motors|servo|all`, vitesse faible) ; fonctionne en mock sur PC.
- **`acquisition_manager.py` / `sensors/soil_sensor.py`** — décrits plus haut.

---

## Décisions d'architecture importantes

- **Pas de N/P/K, pas de rainfall** : le périmètre se limite à pH, humidité, température et EC (température + humidité mesurées sur l'ESP32, pH + EC synthétisés à partir d'elles). Le générateur de dataset et `preprocess.py` lèvent une exception si une de ces variables hors périmètre fuite. Côté chatbot, le LLM ne prétend jamais avoir mesuré N/P/K et ne recommande pas d'engrais NPK (une évocation pédagogique du rôle d'un nutriment reste tolérée). Le modèle de production n'utilise que les 4 variables capteur.
- **Dataset synthétique calibré sur les règles** : le ML n'est pas entraîné sur des CSV externes mais sur un dataset généré à partir des plages exactes de `rules/crop_catalog.py`, avec 85 % au cœur / 15 % bordure. Conséquence : la frontière apprise par le ML reste cohérente avec la vérité agronomique, mais avec des décisions plus tranchées qu'une règle binaire dans les cas ambigus.
- **Moteur de règles comme fallback automatique** : si `best_model.pkl` est absent, `ml_model/predict.py` bascule sur `rules/engine.py`. Aucune exception n'est levée — la démo ne casse jamais.
- **État runtime + persistance légère** : `APP_STATE` reste un singleton Python pour l'état courant. Le plan de mission et les mesures sont persistés dans SQLite (`.agribotics/state.sqlite3` par défaut) et restaurés au redémarrage du backend. La commande robot (`requested`/`running`/`done`) reste volontairement volatile.
- **Chatbot = mise en forme linguistique uniquement** : toute l'inférence agronomique est déterministe (règles) ou ML (scikit). Le LLM Gemini reçoit les résultats déjà calculés et les reformule en FR/AR/Darija.
- **LLM dans le cloud (Gemini), inférence locale** : choix assumé de déporter *uniquement* la couche conversationnelle vers Gemini (Google AI Studio) pour ne pas consommer la RAM locale (l'ancien Ollama/Qwen mobilisait ~2-5 Go). Le cœur métier (ML + règles) reste 100 % local et fonctionne hors-ligne ; seul `/api/chat` requiert internet + `GEMINI_API_KEY`. Aucune donnée personnelle transmise — uniquement le message et le contexte agronomique (4 variables + culture recommandée).
- **Double frontend** : `frontend_simulation` fonctionne sans backend (démo, présentation) ; `frontend_real_backend` est lié au robot.
- **Configuration via `.env` seule** : pour basculer entre machines, seules les variables `GEMINI_API_KEY` et `GEMINI_MODEL` changent. Aucun code touché.

---

## Points connus à compléter

Reste à faire, surtout sur le robot réel (non testable sur PC) :

- **Calibration robot** : `adeept_controller.py` pilote réellement moteurs + servo, mais `DRIVE_THROTTLE_SCALE`, `ROBOT_SPEED_MPS` et les angles de braquage doivent être **calibrés sur le robot**, et le sens des moteurs vérifié (`hardware_test.py`).
- **Navigation précise** : le robot visite les points dans l'ordre du plan, déplacement en **dead-reckoning temporisé** (pas d'encodeurs). Pour plus de précision : brancher le suiveur de ligne / des encodeurs sur `move_to_point` (interface inchangée).
- **Sonde motorisée** : trois drivers disponibles, sélectionnés par `build_probe()` par ordre de priorité : (1) `PiGpioNemaProbeController` — sonde **NEMA pilotée DIRECTEMENT par les GPIO de la Pi** (`PROBE_NEMA_GPIO=1`, driver A4988/DRV8825 sur STEP=GPIO26/DIR=GPIO27, mouvement temporisé avec **rampe d'accél./décél.** pour éviter le décrochage ; sens validés DESCENTE=`L`/REMONTÉE=`H`, course 9 s @ 150 tr/min) ; (2) `Esp32ProbeController` — sonde NEMA pilotée par un **ESP32 en USB série** (`PROBE_SERIAL_PORT`, protocole `DOWN`/`UP` + accusé `OK` bloquant ; firmware `deploy/esp32_probe/esp32_probe.ino`) ; (3) `AdeeptProbeController` (servo, `PROBE_SERVO_CHANNEL`). Sans aucun des trois : descente simulée.
- **Capteur de sol** : température + humidité réelles via ESP32 (`ESP32_SENSOR_PORT`), pH + EC synthétisés à partir d'elles (`SoilSynthesizer`). Validé sur la Pi. Repli simulation automatique si l'ESP32 est débranché.
- Refactor backend en `models/` / `services/` / `routes/` — backend mono-fichier `app.py` aujourd'hui (acceptable).

Déjà fait depuis les versions antérieures : couche robot/sonde (`raspberry_pi/robot/`), `hardware_test.py`, persistance SQLite, `/health` + `/api/status`, arrêt d'urgence, rafraîchissement live du frontend pendant la mission (polling 1,5 s dans `runtime_real.js`, arrêt automatique en fin de mission), **résilience réseau du robot** (file hors-ligne `offline_buffer.py`, zéro perte de mesure), **déploiement systemd** (`deploy/`, démarrage auto au boot), dépendances robot dans `requirements.txt`, suite de tests `unittest` (`tests/`).

### Déploiement (`deploy/`)

Pour un vrai prototype, `deploy/agribotics-backend.service` et `deploy/agribotics-robot.service` (systemd) démarrent le backend et le robot `--watch` automatiquement au boot et les relancent en cas de crash. Procédure d'installation (groupes I2C/série, activation I2C, test matériel) dans `deploy/README.md`. Pour le dev local, `start_demo.sh` reste le lanceur une-commande.

Ces points ne bloquent pas la chaîne logicielle complète actuelle.
