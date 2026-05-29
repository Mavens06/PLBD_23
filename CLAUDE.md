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
`gemini-2.0-flash`) — **aucun changement de code requis** entre machines.

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

### Raspberry Pi / robot (mock sur PC ou hardware sur Pi)
```bash
# Mission complète 3×3 (alimente le backend en 9 mesures)
APP_MODE=mock ./.venv/bin/python -m raspberry_pi.main

# Un seul point
APP_MODE=mock ./.venv/bin/python -m raspberry_pi.main --point B2

# Sur le robot réel : APP_MODE=hardware
APP_MODE=hardware python3 -m raspberry_pi.main
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
| `GEMINI_API_KEY` | _(vide)_ | Clé API Google AI Studio (obligatoire pour le chatbot) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Modèle Gemini servi (flash / flash-lite / 1.5-flash) |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` | Endpoint Generative Language API |
| `GEMINI_TIMEOUT` | `60` | Timeout HTTP de l'appel Gemini (s) |
| `RS485_PORT` | `/dev/ttyUSB0` | Port série du capteur (ou `/dev/ttyAMA0`) |
| `RS485_ADDRESS` | `1` | Adresse Modbus du capteur |
| `RS485_BAUDRATE` | `9600` | Débit série |
| `RS485_TIMEOUT_S` | `0.5` | Timeout de lecture série |
| `SENSOR_MOCK_PROFILE` | `None` | En mock, force le profil d'une zone (`A1`..`C3`) |
| `AGRIBOTICS_API_BASE` | `http://127.0.0.1:8000` | URL du backend pour `raspberry_pi/main.py` |
| `CORS_ORIGINS` | `*` | Origines CORS autorisées par la FastAPI |

---

## Arborescence réelle

```
PLBD/
├── backend/                            # API FastAPI 100 % locale
│   ├── app.py                          # 9 routes : /, chat, mission, measurements, recommendation
│   ├── chatbot_llm.py                  # Client Gemini async (httpx), prompt anti-NPK
│   ├── state.py                        # APP_STATE singleton (RobotState + Measurement + history)
│   ├── .env.example
│   └── __init__.py
│
├── ml_model/                           # Inférence + règles agronomiques + pipeline ML
│   ├── predict.py                      # predict_top_crops() — ML si dispo, sinon rules
│   ├── rules/
│   │   ├── crop_catalog.py             # 10 cultures × 4 plages (pH, humidité, temp, EC)
│   │   └── engine.py                   # Score pondéré + top_k + salinity_alert
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
│   ├── main.py                         # Orchestrateur mission 3×3, push HTTP backend
│   ├── acquisition_manager.py          # Stabilisation 4 s + 10 lectures + stats
│   ├── sensors/
│   │   └── rs485_4in1.py               # Driver unifié RS485 (hardware ou mock auto)
│   ├── sensors.py                      # Stub historique (commentaire)
│   ├── robot_car.py                    # Stub historique (commentaire)
│   └── camera.py                       # Stub historique (commentaire)
│
├── frontend/
│   ├── frontend_simulation/            # Démo autonome — port 5501
│   │   ├── agribotics_v5.html
│   │   ├── css/style.css
│   │   └── js/ (data_model.js, map.js, app.js, chatbot.js, api.js, i18n.js, ...)
│   └── frontend_real_backend/          # Consomme l'API FastAPI — port 5500
│       └── (mêmes fichiers que la version simulation, api.js connecté)
│
├── .venv/                              # Environnement Python 3.12+
├── .env                                # Variables d'environnement (à créer)
├── requirements.txt
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
  même flux, mais _MockSensor produit des lectures cohérentes avec les
  profils de zone du frontend (humidité/pH/temp/EC par zone).

UI :
  frontend_real_backend appelle GET /api/mission, /api/measurements,
  /api/recommendation. Le chatbot appelle POST /api/chat.
```

### Backend (`backend/`)

- **`app.py`** — Application FastAPI mono-fichier. Enregistre toutes les routes et le middleware CORS. Importe les helpers via `from .chatbot_llm`, `from .state` et `from ml_model.predict` (les packages `backend/` et `ml_model/` sont frères à la racine).
- **`state.py`** — Singleton `APP_STATE` (dataclasses) : `RobotState` (status, active_point, progress_pct), dict `measurements_by_zone`, liste `history`. Pas de persistance API — l'état se reset au redémarrage du serveur.
- **`chatbot_llm.py`** — Client **Gemini** (Google AI Studio, cloud) async (httpx), endpoint `generateContent`. Le prompt système passe par `system_instruction`, la question par `contents`. Compose un prompt système strict :
  - mention explicite des 4 variables capteur (pH, humidité, température, EC)
  - **interdiction explicite N/P/K** dans le prompt
  - liste des 10 cultures cibles uniquement
  - langue forcée selon `language` (`fr` / `ar` / `da`)
- **`__init__.py`** — Marque `backend/` comme package Python.

### Routes API

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/` | Healthcheck + config Gemini courante |
| POST | `/api/chat` | Question agriculteur → réponse LLM contextualisée |
| GET | `/api/mission` | État robot + progression |
| POST | `/api/mission/reset` | Vide l'état mémoire |
| GET | `/api/measurements` | `latest` + `history` + `by_zone` |
| POST | `/api/measurements` | Push d'une mesure (depuis robot ou démo) |
| GET | `/api/recommendation` | Top-k cultures pour toutes zones mesurées |
| GET | `/api/recommendation/{point}` | Top-k cultures pour une zone |
| GET | `/api/recommendation/{point}/explain` | Classement complet 10 cultures + détail par variable |

### Capteur RS485 4-en-1 (`raspberry_pi/sensors/`)

- **`rs485_4in1.py`** — `build_sensor()` retourne automatiquement :
  - `_HardwareSensor` (minimalmodbus) si `APP_MODE=hardware`
  - `_MockSensor` sinon (profils de zone identiques au frontend)
  
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
- **`data_loader.py`** — `generate_dataset(samples_per_crop=1000)` produit un DataFrame de N×10 lignes avec colonnes `[ph, humidity, temperature, ec, label]`. Pour chaque culture : **85 %** au cœur de la plage (bruit σ = width × 0.05), **15 %** en bordure (σ = width × 0.10). Les tirages franchement hors-plage sont désactivés (`out_frac=0.0`) car ils constituaient du bruit d'étiquetage. Clamping physique automatique (pH ∈ [3, 10], EC ∈ [0, 12], …). `FEATURE_ORDER = ["ph", "humidity", "temperature", "ec"]` — **cet ordre est partagé avec preprocess.py et predict.py**.
- **`data_preparation.py`** — Wrapper de `data_loader.generate_dataset()` qui sauvegarde `data/final_dataset.csv` et lève `RuntimeError` si une colonne hors périmètre (N/P/K/rainfall) apparaît. Exécution : `python ml_model/data_preparation.py`.
- **`preprocess.py`** — Charge le CSV, vérifie qu'aucune colonne hors périmètre n'a fuité, split stratifié 80/20 (`random_state=42`), `StandardScaler` ajusté sur le train set seulement et sauvegardé.
- **`train.py`** — Entraîne 4 modèles candidats avec **StratifiedKFold k=5** et score CV `f1_macro`, puis évaluation finale sur le test set (Accuracy, Précision/Rappel pondérés, F1-macro, F1-pondéré). Sélection par F1-macro (tiebreak : F1-pondéré, puis accuracy). Sauvegarde `best_model.pkl` + `scaler.pkl`. Modèles : `RandomForestClassifier(n_estimators=300)`, `SVC(kernel="rbf", C=10, probability=True)`, `GradientBoostingClassifier(n_estimators=200)`, `LogisticRegression(max_iter=2000)`.
- **`predict.py`** — `predict_top_crops(ph, humidity, temperature, ec, k=3)` :
  - charge `best_model.pkl` + `scaler.pkl` si disponibles → `engine: "ml"` (ordre de features = `FEATURE_ORDER`)
  - sinon ou en cas d'erreur de chargement/version → bascule silencieusement sur le moteur de règles → `engine: "rules"`
  - retourne `{engine, top: [{crop, score, details}], alerts: [...]}`
  - mapping sémantique : `humidity` (capteur) ↔ `humidity` (ML), `ec` (capteur) ↔ `salinity` (alerte) ↔ `ec` (feature ML)
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

**Variables affichées dans la carte / les jauges** : les 4 du capteur — humidité, pH, température, EC. L'EC est traitée comme variable de première classe (jauge dédiée, couche carte, alerte salinité visuelle).

**Chatbot** (`js/chatbot.js`) : envoie au backend `selected_zone`, `selected_crop`, `zone_data`, `robot_state`. Fonction `localAnswer()` de secours qui produit une réponse FR/AR/Darija déterministe sans LLM si le backend n'est pas joignable.

### Raspberry Pi (`raspberry_pi/`)

- **`main.py`** — Orchestrateur de mission. Argparse : `--point B2` (zone unique) ou pas d'argument (mission 3×3 complète). Reset du backend en début de mission, push HTTP par mesure, log console détaillé.
- **`acquisition_manager.py` / `sensors/rs485_4in1.py`** — décrits plus haut.
- **`sensors.py`, `robot_car.py`, `camera.py`** — stubs commentaires historiques ; **non utilisés** par le pipeline actif.

---

## Décisions d'architecture importantes

- **Pas de N/P/K, pas de rainfall** : le capteur 4-en-1 RS485 mesure uniquement pH, humidité, température et EC. Le générateur de dataset, `preprocess.py` et le prompt système Gemini vérifient et interdisent toute fuite de ces variables hors périmètre. Toute tentative déclenche une exception.
- **Dataset synthétique calibré sur les règles** : le ML n'est pas entraîné sur des CSV externes mais sur un dataset généré à partir des plages exactes de `rules/crop_catalog.py`, avec 85 % au cœur / 15 % bordure. Conséquence : la frontière apprise par le ML reste cohérente avec la vérité agronomique, mais avec des décisions plus tranchées qu'une règle binaire dans les cas ambigus.
- **Moteur de règles comme fallback automatique** : si `best_model.pkl` est absent, `ml_model/predict.py` bascule sur `rules/engine.py`. Aucune exception n'est levée — la démo ne casse jamais.
- **État en mémoire** : `APP_STATE` est un singleton Python. Redémarrer le backend remet l'état à zéro. Pas de SQLite côté backend pour l'instant (à ajouter côté robot si persistance souhaitée).
- **Chatbot = mise en forme linguistique uniquement** : toute l'inférence agronomique est déterministe (règles) ou ML (scikit). Le LLM Gemini reçoit les résultats déjà calculés et les reformule en FR/AR/Darija.
- **LLM dans le cloud (Gemini), inférence locale** : choix assumé de déporter *uniquement* la couche conversationnelle vers Gemini (Google AI Studio) pour ne pas consommer la RAM locale (l'ancien Ollama/Qwen mobilisait ~2-5 Go). Le cœur métier (ML + règles) reste 100 % local et fonctionne hors-ligne ; seul `/api/chat` requiert internet + `GEMINI_API_KEY`. Aucune donnée personnelle transmise — uniquement le message et le contexte agronomique (4 variables + culture recommandée).
- **Double frontend** : `frontend_simulation` fonctionne sans backend (démo, présentation) ; `frontend_real_backend` est lié au robot.
- **Configuration via `.env` seule** : pour basculer entre machines, seules les variables `GEMINI_API_KEY` et `GEMINI_MODEL` changent. Aucun code touché.

---

## Points connus à compléter

Ces éléments mentionnés dans des versions antérieures de la doc ne sont **pas** encore implémentés :

- `raspberry_pi/robot/motors.py` — pilotage PCA9685 + TB6612FNG (driver moteurs Adeept Pi Car). Actuellement le déplacement est un stub `_move_to()` qui log.
- `raspberry_pi/robot/navigation.py` — grille 4×6 (24 points, espacement 3 m). Actuellement, grille 3×3 (9 points) cohérente avec le frontend.
- `raspberry_pi/robot/safety.py` — vérifications avant déplacement / mesure.
- `raspberry_pi/storage/sqlite_db.py` — SQLite local résilient hors-ligne sur le robot.
- `backend/services/weather_service.py` — appel Open-Meteo (sans clé) pour enrichir les recos avec la météo.
- `frontend/.../live.js` — polling automatique toutes les 3 s du backend. Actuellement, rafraîchissement manuel.
- Refactor backend en `models/` / `services/` / `routes/` — backend mono-fichier `app.py` aujourd'hui. Acceptable tant que la taille reste raisonnable.
- Tests automatisés (pytest) — actuellement tests manuels via curl + `raspberry_pi/main.py`.

Ces points ne bloquent pas la démo logicielle complète actuelle.
