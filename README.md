# Agribotics — robot agricole de mesure de sol (PLBD)

Prototype fonctionnel d'un robot agricole mobile (**Adeept PiCar-Pro** + **Raspberry Pi**)
qui visite des points d'une parcelle, **mesure le sol** (pH, humidité, température, EC)
et produit des **recommandations de culture** multilingues (FR / AR / Darija) avec un chatbot.

Acquisition du sol : **température (DS18B20) + humidité (capteur capacitif)** lues en réel
sur un **ESP32 en USB série** ; **pH + EC générés de façon agronomiquement cohérente à
partir** de ces deux valeurs réelles. État : chaîne complète opérationnelle (robot,
mission, backend, ML/règles, interface, chatbot).

- **Inférence agronomique 100 % locale** (ML scikit-learn + moteur de règles).
- **Seul le chatbot** utilise le cloud (LLM **Gemini**, Google AI Studio).

---

## Installation

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp backend/.env.example .env          # puis renseigner GEMINI_API_KEY
```

Sur Raspberry Pi (matériel réel), installer aussi les libs robot :
`adafruit-circuitpython-pca9685`, `adafruit-circuitpython-motor`, `RPi.GPIO`,
`gpiozero` (non requises sur PC de dev — la couche robot bascule en mock).

---

## Lancement rapide (toute la chaîne, une commande)

```bash
./start_demo.sh                       # PC, mode mock (sans matériel)
APP_MODE=hardware ./start_demo.sh     # Raspberry Pi, robot réel
```

Lance le backend (`:8000`), le robot en mode `--watch` et le frontend réel (`:5500`).
Ouvrir **http://localhost:5500**. `Ctrl-C` arrête les trois processus.

### Ou manuellement (3 terminaux)

```bash
# 1. Backend
./.venv/bin/python -m uvicorn backend.app:app --reload --host 0.0.0.0

# 2. Robot (daemon piloté par l'interface)
APP_MODE=mock ./.venv/bin/python -m raspberry_pi.main --watch

# 3. Frontend réel
cd frontend/frontend_real_backend && python3 -m http.server 5500
```

Frontend de **simulation** autonome (sans backend) : `frontend/frontend_simulation` (port 5501).

---

## Flux d'une mission

```
Interface → POST /api/mission/plan (N points)
          → POST /api/mission/start (command=requested)
   Robot (--watch) détecte l'ordre et, pour chaque point :
          déplacement → descente sonde → stabilisation → mesure capteur
          → remontée sonde → POST /api/measurements
   Backend → recommandation (ML + règles) → interface → chatbot
   Arrêt d'urgence : POST /api/mission/stop → robot stoppe entre 2 points
```

### Vérifications utiles

```bash
curl http://localhost:8000/health        # {"status":"ok",...}
curl http://localhost:8000/api/status    # mission, mode, dernière mesure + reco, LLM
```

---

## Chatbot vocal multilingue (FR / AR / Darija)

Le chatbot reformule en langage naturel les résultats déjà calculés localement
(ML + règles) — il **n'invente aucune mesure ni recommandation**. Trois briques
cloud, toutes **découplées** et configurables via `.env` (provider `gemini` par
défaut, ou `openai`) :

| Brique | Route | Rôle |
|---|---|---|
| Chat | `POST /api/chat` | Question → réponse experte contextualisée |
| Voix (TTS) | `POST /api/tts` | Réponse → audio (vraie voix arabe) |
| **Micro (STT)** | `POST /api/stt` | **Parole → texte (transcription)** |

### Reconnaissance vocale (STT)

La reconnaissance vocale **intégrée au navigateur** (Web Speech API) déchiffre
mal l'arabe et quasiment pas la darija. La parole est donc enregistrée côté
navigateur (`MediaRecorder`, arrêt automatique au silence) puis transcrite par
un service **cloud** bien plus fiable (**OpenAI Whisper / `gpt-4o-transcribe`**,
ou Gemini), via la route `POST /api/stt`. **Repli automatique** sur la
reconnaissance locale si le cloud échoue ou le micro est refusé.

```bash
# .env — provider de la transcription (vide = suit LLM_PROVIDER)
STT_PROVIDER=openai            # Whisper, recommandé en arabe/darija
OPENAI_STT_MODEL=gpt-4o-transcribe
```

> ⚠️ **Le micro (`getUserMedia`) exige un contexte sécurisé (HTTPS ou
> `localhost`)** : en accès LAN direct (`http://<ip>:5500`) la capture est
> bloquée par le navigateur — passer par un tunnel HTTPS. La darija (`da`) est
> transcrite en lettres arabes (mappée sur `ar`).

---

## Matériel robot (Adeept PiCar-Pro)

Pilotage réel via **PCA9685** (`adafruit_motor`) : 2 moteurs DC + 1 servo de
direction. Couche isolée dans `raspberry_pi/robot/` (interfaces dans `base.py`,
mock pour le PC, `adeept_controller.py` pour la Pi). Mapping et calibration
**configurables par `.env`** (cf. `backend/.env.example`).

Test matériel sûr (robot sur support, vitesse faible) :

```bash
APP_MODE=hardware python3 -m raspberry_pi.hardware_test --test motors
APP_MODE=hardware python3 -m raspberry_pi.hardware_test --test servo
APP_MODE=hardware python3 -m raspberry_pi.hardware_test --test all
```

> Déplacement point-à-point : *dead-reckoning temporisé* (durée ∝ distance,
> vitesse `ROBOT_SPEED_MPS`), faute d'odométrie/encodeurs sur ce robot.

---

## Déploiement (Raspberry Pi, démarrage automatique)

Pour un vrai prototype, le backend et le robot démarrent au boot via systemd
(`deploy/agribotics-backend.service`, `deploy/agribotics-robot.service`) et se
relancent en cas de crash. Procédure complète : **`deploy/README.md`**.

**Résilience réseau** : si le backend est injoignable pendant une mission, le
robot ne perd aucune mesure — elles sont mises en file sur le disque
(`AGRIBOTICS_ROBOT_OUTBOX`) et retransmises automatiquement à la mission suivante.

## Capteurs (à venir)

La lecture du sol est isolée dans `raspberry_pi/sensors/` (`build_sensor()`).
En `APP_MODE=hardware` avec `ESP32_SENSOR_PORT` défini, la température + humidité
viennent de l'ESP32 et le pH + EC sont synthétisés à partir d'elles
(`SoilSynthesizer`). Sans ESP32 (ou `APP_MODE=mock`), un mock cohérent prend le
relais, **sans changer le backend, le ML ni l'interface**.

---

## Modèle ML

- 10 cultures cibles (Blé, Tomate, Oignon, Carotte, Pomme de terre, Orge,
  Betterave à sucre, Olivier, Vigne, Pastèque), 4 variables capteur (pH,
  humidité, température, **EC**).
- `ml_model/best_model.pkl` (production). Si absent → bascule automatique sur le
  moteur de règles. Réentraîner : `./.venv/bin/python ml_model/train.py`.

Détails d'architecture : voir `CLAUDE.md`.

---

## Tests

```bash
./.venv/bin/python -m unittest discover -s tests -q
```
