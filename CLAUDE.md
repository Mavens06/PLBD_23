# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Vue d'ensemble

**Agribotics** est un prototype académique réel de robot agricole mobile basé sur une **Raspberry Pi** (châssis **Adeept Pi Car Pro**). Le robot navigue sur des points prédéfinis d'une parcelle, acquiert des mesures de sol via un **capteur industriel 4-en-1 RS485 (Modbus RTU)** et génère des recommandations agronomiques multilingues (FR / AR / Darija marocaine).

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

`minimalmodbus` est installé automatiquement uniquement sur architectures ARM (Raspberry Pi). Sur PC/Mac de dev, il n'est pas requis car on tourne en mode `mock`.

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

# Essai complet SANS capteur RS485 : robot + bras réels, mesures simulées
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
| `SENSOR_MODE` | `auto` | `auto` = suit `APP_MODE` · `mock` = mesures simulées même en hardware (essai complet sans capteur RS485) · `hardware` = force le RS485 (repli mock si init KO) |
| `SENSOR_MOCK_OUTLIER_RATE` | `0` | Probabilité [0..1] qu'un point mock produise des valeurs aberrantes (salinité, pH acide, sol sec, temp « suspect ») |
| `SENSOR_MOCK_OUTLIER_POINTS` | _(vide)_ | Labels forcés en aberrant, ex. `B2,C1` |
| `GEMINI_API_KEY` | _(vide)_ | Clé API Google AI Studio (obligatoire pour le chatbot) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Modèle Gemini servi (2.5-flash / 2.5-flash-lite) |
| `GEMINI_FALLBACK_MODEL` | `gemini-2.5-flash-lite` | Modèle de repli si le principal renvoie 429 (quota) ; vide = désactivé |
| `GEMINI_TTS_MODEL` | `gemini-2.5-flash-preview-tts` | Modèle TTS Gemini pour la route `/api/tts` (vraie voix arabe) |
| `GEMINI_TTS_VOICE` | `Kore` | Voix prédéfinie Gemini (parle la langue du texte) |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` | Endpoint Generative Language API |
| `GEMINI_TIMEOUT` | `60` | Timeout HTTP de l'appel Gemini (s) |
| `RS485_PORT` | `/dev/ttyUSB0` | Port série du capteur (ou `/dev/ttyAMA0`) |
| `RS485_ADDRESS` | `1` | Adresse Modbus du capteur |
| `RS485_BAUDRATE` | `9600` | Débit série |
| `RS485_TIMEOUT_S` | `0.5` | Timeout de lecture série |
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
| `TURN_THROTTLE` | `0.18` | Throttle pendant les virages en arc |
| `TURN_90_S` | `1.2` | Durée d'un quart de tour en arc (~90°) |
| `ROBOT_SPEED_MPS` | `0.19` | Vitesse ligne droite (≈35-40 cm en 2 s, validé) |
| `ROBOT_WORLD_SCALE` | `1.0` | Échelle plan→physique : démo 1 m × 1 m avec grille 6 m → `0.15`. N'affecte ni l'UI ni les mesures |
| `ROBOT_RETURN_HOME` | `0` | `1` = retour à (0,0) en fin de mission (jamais après arrêt d'urgence) |
| `OBSTACLE_AVOIDANCE` / `OBSTACLE_MIN_DISTANCE_CM` / `OBSTACLE_TIMEOUT_S` | `1` / `12` / `20` | Ultrason anti-obstacle (trigger 23 / écho 24) : pause + reprise auto, abandon propre au timeout |
| `SIGNALS_ENABLED` / `LED_PINS` / `BUZZER_PIN` | `1` / `25,11` / `18` | LEDs + buzzer (bips mission, clignotement par point, alerte obstacle) — no-op si absents |
| `PROBE_SERVO_CHANNEL` | _(vide)_ | Canal de l'ÉPAULE du bras-sonde (validé : `2`) ; vide = descente simulée |
| `PROBE_ANGLE_UP/DOWN` / `PROBE_ARM_HOME` | `90/150` / `1:90,3:140,4:80` | Angles épaule haut/bas + posture home des autres servos du bras |

---

## Arborescence réelle

```
PLBD/
├── backend/                            # API FastAPI 100 % locale
│   ├── app.py                          # Routes : /health, /api/status, chat, tts, mission, measurements, recommendation
│   ├── chatbot_llm.py                  # Client Gemini async (httpx) : chat conversationnel + TTS
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
│   │   └── __init__.py                 # build_robot() / build_probe() selon APP_MODE
│   ├── offline_buffer.py               # File hors-ligne des mesures (résilience réseau)
│   └── sensors/
│       └── rs485_4in1.py               # Driver unifié RS485 (hardware ou mock auto)
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
      → _HardwareSensor.read() × 10  (stabilisation 4 s + 10 lectures Modbus 0x03)
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
| GET | `/api/mission` | État robot + progression + `plan` + `command` |
| GET | `/api/mission/plan` | Plan de mission courant (liste de points `{label, x, y}`) — lu par le robot |
| POST | `/api/mission/plan` | Définit le plan de mission depuis l'interface (N points x/y) |
| POST | `/api/mission/start` | Commande le démarrage (`command="requested"`) — le robot `--watch` exécute |
| POST | `/api/mission/end` | Demande l'arrêt (abort) de la mission |
| POST | `/api/mission/stop` | **Arrêt d'urgence** : `command=idle` + `emergency_stop` ; le robot `--watch` stoppe entre 2 points |
| POST | `/api/mission/reset` | Vide l'état mémoire (conserve le plan) |
| GET | `/api/measurements` | `latest` + `history` + `by_zone` |
| POST | `/api/measurements` | Push d'une mesure (depuis robot ou démo) |
| GET | `/api/recommendation` | Top-k cultures pour toutes zones mesurées |
| GET | `/api/recommendation/{point}` | Top-k cultures pour une zone |
| GET | `/api/recommendation/{point}/explain` | Classement règles 10 cultures + détail par variable (+ `ml_top` si modèle dispo) |
| GET | `/api/recommendation/{point}/correction?crop=X` | Diagnostic du sol pour une culture cible + corrections + cultures mieux adaptées |

### Capteur RS485 4-en-1 (`raspberry_pi/sensors/`)

- **`rs485_4in1.py`** — `build_sensor()` retourne automatiquement :
  - `_HardwareSensor` (minimalmodbus) si le mode capteur résolu est `hardware` (avec **repli mock** si l'init échoue : port absent, lib manquante)
  - `_MockSensor` sinon. Priorité aux profils curés A1..C3 (démo) ; pour tout autre point, **`soil_at(x, y)`** — champ de sol synthétique déterministe et spatialement cohérent (miroir exact de `soilAt()` dans `js/data_model.js`). `set_location(label, x, y)` positionne le mock.

  Le mode capteur est **découplé du mode robot** : `SENSOR_MODE` (`auto`/`mock`/`hardware`, défaut `auto` = suit `APP_MODE`). `APP_MODE=hardware SENSOR_MODE=mock` = mode « essai complet sans capteur RS485 » (robot et bras réels, mesures simulées en temps réel). Le mock peut **injecter des profils aberrants** (`SENSOR_MOCK_OUTLIER_RATE` probabiliste et/ou `SENSOR_MOCK_OUTLIER_POINTS` forcés) : `saline` (EC 7.2 → alerte salinité), `acide` (pH 3.5), `sec` (humidité 4 %), `canicule` (57 °C → qualité `suspect`). Les profils restent dans les bornes acceptées par le backend (pas de 422) pour exercer les garde-fous **en aval**.
  
  Registres lus en un seul bloc Modbus (fonction 0x03) :
  ```
  Reg 0x0000 → moisture     × 0.1 %
  Reg 0x0001 → temperature  × 0.1 °C   (signé 16 bits — two's complement)
  Reg 0x0002 → conductivity   µS/cm    (converti en mS/cm)
  Reg 0x0003 → ph           × 0.1
  ```
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

- **`main.py`** — Orchestrateur de mission piloté par le **plan dynamique**. Source du plan par priorité : `--plan plan.json` → `GET /api/mission/plan` → repli grille 3×3. Argparse : `--point`, `--plan`, `--watch` (**daemon** déclenché par `command=="requested"`), `--no-reset`. **Séquence par point** : `robot.move_to_point` → `probe.lower_probe` → `probe.stabilize` → acquisition capteur → `probe.raise_probe` → push HTTP. **Résilience réseau** : un push raté n'est jamais perdu — la mesure est mise en file sur le disque (`offline_buffer.OfflineBuffer`) et retransmise au début de la mission suivante. **Arrêt d'urgence** : en `--watch`, `should_abort` détecte `command` repassé à `idle` (via `/api/mission/stop` ou `/end`) et stoppe entre deux points ; le robot est toujours arrêté en fin de mission (`finally`).
- **`offline_buffer.py`** — File d'attente disque (JSON Lines) des mesures non transmises au backend. `enqueue()` persiste immédiatement, `flush(push_fn)` retransmet (s'arrête au premier échec pour ne pas marteler le réseau), tolère un fichier corrompu. Garantit **zéro perte de mesure** au champ.
- **`robot/`** — Couche robot/sonde **isolée** (même logique que `sensors.build_sensor`). `base.py` : interfaces `RobotController` / `ProbeController`. `mock_controller.py` : implémentations simulées (PC / repli). `adeept_controller.py` : pilotage **réel** du PiCar-Pro, calqué sur le code mission **validé sur le robot** (`Code_PLBD_23_mission.py`) : PCA9685 `adafruit_motor`, 2 moteurs DC + servo de direction (centre 85°, braquages à fond 0°/180°), **throttles signés** (avant = `-0.15`, virages = `+0.18` — ne pas « corriger » sans réessai), **virages en arc** (braquage à fond + avance `TURN_90_S`), navigation **Manhattan par cap N/E/S/W** (`manhattan_legs()`, fonction pure testée). **`ROBOT_WORLD_SCALE`** rejoue le plan (mètres UI) sur une surface réduite (démo 1 m²) sans toucher UI/backend/mesures. Bras-sonde 4 servos (épaule canal 2 descend, posture home `1:90,3:140,4:80`). **Ultrason anti-obstacle** (trigger 23 / écho 24, seuil 12 cm) vérifié toutes les ~0.4 s pendant les lignes droites : pause + LED + bip puis reprise auto quand la voie se dégage, `RuntimeError` propre au timeout (le daemon `--watch` survit). **LEDs/buzzer** (`signals.py`, GPIO 25/11 + 18) : bips mission, clignotement par point — no-op silencieux si gpiozero/broches absents. `__init__.py` : `build_robot()` / `build_probe()` selon `APP_MODE`, avec repli mock si l'I2C échoue. Limite assumée : pas d'odométrie → **dead-reckoning temporisé** (`ROBOT_SPEED_MPS`).
- **`hardware_test.py`** — Test matériel sûr (`--test motors|servo|all`, vitesse faible) ; fonctionne en mock sur PC.
- **`acquisition_manager.py` / `sensors/rs485_4in1.py`** — décrits plus haut.

---

## Décisions d'architecture importantes

- **Pas de N/P/K, pas de rainfall** : le capteur 4-en-1 RS485 mesure uniquement pH, humidité, température et EC. Le générateur de dataset et `preprocess.py` lèvent une exception si une de ces variables hors périmètre fuite. Côté chatbot, le LLM ne prétend jamais avoir mesuré N/P/K et ne recommande pas d'engrais NPK (une évocation pédagogique du rôle d'un nutriment reste tolérée). Le modèle de production n'utilise que les 4 variables capteur.
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
- **Sonde motorisée** : `AdeeptProbeController` (servo) est prêt, activé dès que `PROBE_SERVO_CHANNEL` est défini ; en attendant, descente simulée.
- **Capteur RS485** : driver `_HardwareSensor` prêt, activé en `APP_MODE=hardware` dès le montage du capteur — sans changer le backend, le ML ni l'interface.
- Refactor backend en `models/` / `services/` / `routes/` — backend mono-fichier `app.py` aujourd'hui (acceptable).

Déjà fait depuis les versions antérieures : couche robot/sonde (`raspberry_pi/robot/`), `hardware_test.py`, persistance SQLite, `/health` + `/api/status`, arrêt d'urgence, rafraîchissement live du frontend pendant la mission (polling 1,5 s dans `runtime_real.js`, arrêt automatique en fin de mission), **résilience réseau du robot** (file hors-ligne `offline_buffer.py`, zéro perte de mesure), **déploiement systemd** (`deploy/`, démarrage auto au boot), dépendances robot dans `requirements.txt`, suite de tests `unittest` (`tests/`).

### Déploiement (`deploy/`)

Pour un vrai prototype, `deploy/agribotics-backend.service` et `deploy/agribotics-robot.service` (systemd) démarrent le backend et le robot `--watch` automatiquement au boot et les relancent en cas de crash. Procédure d'installation (groupes I2C/série, activation I2C, test matériel) dans `deploy/README.md`. Pour le dev local, `start_demo.sh` reste le lanceur une-commande.

Ces points ne bloquent pas la chaîne logicielle complète actuelle.
