# Agri-Botics V1 — PLBD_23

Prototype académique d’un robot agricole mobile pour cartographie dynamique du sol.

## Objectif
Le robot se déplace sur des points fixes, insère une sonde sol, mesure **4 capteurs réels** et produit des conseils terrain :
- humidité (%)
- pH
- conductivité / salinité (mS/cm)
- température (°C)

## Architecture V1
- **Raspberry Pi (cerveau principal)** : mission robot, acquisition capteurs, stockage local, exécution locale.
- **Backend FastAPI** : API JSON modulaire (`mission`, `measurements`, `map`, `recommendations`, `weather`, `chat`).
- **Frontend Web** : dashboard léger avec 4 espaces (Terrain, Carte, Conseils, Technique).
- **ML/Règles métier** : moteur léger de scoring cultures + actions pratiques (sans complexité inutile).

## Mapping officiel des variables capteurs
- Schéma runtime (frontend/backend/robot): `humidity`, `ph`, `ec`, `temp`
- Schéma ML (entraînement/inférence): `humidity`, `ph`, `salinity`, `temperature`, `rainfall`
- Mapping unique:
  - `ec -> salinity`
  - `temp -> temperature`
  - `rainfall` provient de la météo (`rain_mm_next_24h`) quand disponible

## Structure du repo
```
PLBD_23/
├── backend/
├── frontend/
├── ml_model/
└── raspberry_pi/
```

## Chatbot
Le chatbot reste textuel + vocal (micro + synthèse vocale) et utilise uniquement les 4 capteurs réels.
Langues supportées :
- Français (`fr`)
- Arabe (`ar`)
- Darija marocaine (`da`)

## Recommandations cultures (catalogue V1)
Maximum 10 cultures :
Blé, Orge, Maïs, Tomate, Pomme de terre, Oignon, Olivier, Agrumes, Luzerne, Pois chiche.

## Lancer localement
### 1) Installation
```bash
pip install -r requirements.txt
```

### 2) Backend
Depuis la racine du repo :
```bash
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

### 3) Frontend
Ouvrir directement :
`frontend/agribotics_v5.html`

(ou servir statiquement le dossier `frontend/` avec un serveur local)

### 4) Raspberry Pi (simulation locale de la boucle)
```bash
python -m raspberry_pi.main
```

## Scenario JSON (mission personnalisable)
Vous pouvez definir un scenario avec vos points et vos parametres de mission:

Exemple de fichier: [raspberry_pi/scenarios/first_demo.json](raspberry_pi/scenarios/first_demo.json)

Lancer le scenario:
```bash
python3 raspberry_pi/main.py --scenario-file raspberry_pi/scenarios/first_demo.json
```

Ou sans fichier scenario:
```bash
python3 raspberry_pi/main.py --points A1,B2,C3 --stabilization 3 --read-count 10
```

## Entrainement modele + preparation chatbot multilingue
Pipeline complet (modele ML + corpus chatbot + test inference):
```bash
python3 scripts/prepare_simulation.py
```

Ce pipeline genere:
- `ml_model/best_model.pkl`
- `ml_model/scaler.pkl`
- `backend/data/chatbot_multilang_train.jsonl`

Generation seule du corpus chatbot:
```bash
python3 backend/chatbot_language_training.py
```

## Réel vs simulé
### Réel dans l’architecture
- séparation claire embarqué / backend / frontend
- logique acquisition robuste (stabilisation + 10 lectures + médiane + dispersion)
- API modulaire prête pour intégration terrain

### Simulé dans cette V1
- valeurs capteurs/cartes en mode démo locale
- commandes moteurs/caméra en stub léger
- météo fournie en données de démonstration

## Prochaines étapes
- connecter les drivers matériels réels capteurs/moteurs
- brancher la météo temps réel
- persister les sessions multi-jours pour analyses temporelles
- améliorer le scoring cultures avec calibration terrain
