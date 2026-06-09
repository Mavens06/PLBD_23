# Plan express 3 jours — Stabilisation du projet Agri-Botics / PLBD

## 0. Objectif réaliste

L’objectif n’est plus de refaire tout le projet. L’objectif est d’obtenir, en **3 jours maximum**, un prototype démontrable, robuste et défendable pour la foire et la soutenance.

Le résultat attendu est le suivant :

> Le robot Adeept PiCar Pro doit pouvoir se déplacer réellement, exécuter une mission simple, s’arrêter sur des points, simuler l’abaissement d’une sonde multi-capteurs, produire des mesures simulées crédibles, envoyer ces mesures au backend local, afficher les résultats dans l’interface web et déclencher les recommandations + chatbot.

Les capteurs réels ne sont pas encore disponibles. Donc le projet doit être conçu de telle sorte que l’acquisition réelle soit simplement remplacée plus tard par un module `RealSensorReader`, sans changer toute l’architecture.

---

## 1. Définition de réussite pour la foire/soutenance

Le prototype est considéré comme prêt si :

- le backend démarre sur la Raspberry Pi ;
- l’interface est accessible depuis un ordinateur sur le même Wi-Fi ;
- une mission peut être lancée depuis l’interface ;
- le robot se déplace réellement ;
- le robot s’arrête à un point ;
- une sonde factice descend et remonte, ou au minimum un servo simule l’action ;
- le système attend quelques secondes pour simuler la stabilisation ;
- une mesure mock est générée : pH, humidité, température, EC ;
- la mesure est sauvegardée ;
- l’interface affiche la mesure ;
- une recommandation est générée ;
- le chatbot explique la recommandation en français, arabe ou darija ;
- un bouton d’arrêt d’urgence permet d’interrompre la mission ;
- le système reste utilisable même sans capteurs réels.

Phrase officielle à utiliser devant le jury :

> L’acquisition réelle des grandeurs physico-chimiques est isolée dans une couche capteur. Aujourd’hui, le robot exécute toute la chaîne de mission avec un mode mock contrôlé ; l’arrivée du capteur nécessitera uniquement l’implémentation du driver de lecture dans cette couche.

---

## 2. Ce qu’il ne faut pas faire en 3 jours

Pour éviter de perdre du temps, il ne faut pas viser :

- une navigation autonome parfaite ;
- une cartographie avancée ;
- une détection d’obstacles complexe ;
- une base de données très sophistiquée ;
- une refonte complète du frontend ;
- un entraînement ML complet avec vraies données ;
- une intégration capteur réelle tant que les capteurs ne sont pas disponibles ;
- une architecture microservices ;
- une application mobile.

La priorité est : **démo stable > architecture parfaite**.

---

## 3. Architecture cible minimale

Architecture à viser :

```text
PLBD/
├── backend/
│   ├── app.py
│   ├── database.py
│   ├── config.py
│   ├── mission_service.py
│   ├── recommendation_service.py
│   ├── chatbot_llm.py
│   └── state.py
│
├── raspberry_pi/
│   ├── mission_runner.py
│   ├── hardware_test.py
│   ├── robot/
│   │   ├── base.py
│   │   ├── mock_controller.py
│   │   ├── adeept_controller.py
│   │   └── probe_controller.py
│   └── sensors/
│       ├── base.py
│       ├── mock_sensor.py
│       └── real_sensor_placeholder.py
│
├── frontend/
│   ├── frontend_real_backend/
│   └── frontend_simulation/
│
├── ml_model/
├── requirements.txt
├── README.md
├── .env.example
└── start_demo.sh
```

Principe important :

```text
Backend = cerveau applicatif
RobotController = déplacement physique
ProbeController = sonde simulée
SensorReader = mesure mock ou réelle
MissionRunner = orchestration complète
Frontend = interface de démonstration
```

---

## 4. Variables d’environnement à prévoir

Créer ou compléter `.env.example` :

```env
# Mode robot
ROBOT_MODE=mock
# valeurs possibles : mock, adeept

# Mode capteurs
SENSOR_MODE=mock
# valeurs possibles : mock, real

# LLM
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key_here
OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-5-mini

# Démo
DEMO_MODE=true
MAX_OUTPUT_TOKENS=600

# Backend
HOST=0.0.0.0
PORT=8000

# Base locale
DATABASE_URL=sqlite:///./agribotics.db
```

Ne jamais mettre le vrai fichier `.env` dans l’archive ou sur GitHub.

---

## 5. Plan de travail condensé sur 3 jours

# Jour 1 — Stabiliser le backend et la chaîne logicielle

## Objectif du jour

Avoir un backend fiable, persistant, testable, qui ne perd pas toutes les données au redémarrage.

## Tâches prioritaires

### 1. Nettoyage

À faire :

- supprimer `.env` des fichiers partagés ;
- garder seulement `.env.example` ;
- vérifier que `.gitignore` contient :

```gitignore
.env
.venv/
__pycache__/
*.pyc
*.db
.git/
frontend.zip
```

### 2. Ajouter `/health`

Endpoint minimal :

```text
GET /health
```

Réponse attendue :

```json
{
  "status": "ok",
  "service": "agribotics-backend"
}
```

### 3. Ajouter `/api/status`

Endpoint :

```text
GET /api/status
```

Il doit retourner :

- état mission ;
- mode robot ;
- mode capteur ;
- dernière mesure ;
- dernière recommandation ;
- disponibilité LLM si possible.

Exemple :

```json
{
  "mission_status": "IDLE",
  "robot_mode": "mock",
  "sensor_mode": "mock",
  "last_measurement": null,
  "last_recommendation": null
}
```

### 4. Ajouter SQLite minimale

Tables minimales :

```text
missions
- id
- name
- status
- created_at
- started_at
- ended_at

mission_points
- id
- mission_id
- point_index
- x
- y
- status

measurements
- id
- mission_id
- point_index
- ph
- humidity
- temperature
- ec
- created_at

recommendations
- id
- measurement_id
- crop
- score
- explanation
- created_at
```

Il n’est pas nécessaire d’avoir une base parfaite. Il faut simplement que les mesures et missions ne disparaissent pas immédiatement au redémarrage.

### 5. Garder les anciens endpoints

Très important : ne pas casser l’interface existante.

Codex doit préserver les routes déjà utilisées par le frontend.

## Prompt Codex — Jour 1

À donner dans le terminal, dans le dossier du projet :

```text
Tu vas solidifier ce projet pour une démonstration réelle sur Raspberry Pi avec un Adeept PiCar Pro.

Priorité 1 : ajoute une persistance SQLite minimale pour missions, points de mission, mesures et recommandations, sans casser les endpoints existants.

Ajoute aussi :
- GET /health
- GET /api/status
- un fichier backend/database.py
- un fichier backend/config.py si nécessaire
- un .env.example propre

Contraintes :
- ne casse pas les routes actuelles du frontend ;
- garde le mode actuel fonctionnel ;
- si une base SQLite est indisponible, le backend doit afficher une erreur claire ;
- documente les changements dans README.md ;
- lance les tests ou au minimum vérifie que le backend démarre avec uvicorn.
```

## Contrôle à faire après Codex

Lancer :

```bash
python -m uvicorn backend.app:app --reload
```

Tester :

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/status
```

Vérifier que le frontend se connecte encore au backend.

## Prompt Claude Code — Revue Jour 1

```text
Fais une revue d’architecture après les modifications de Codex.

Vérifie :
- que la persistance SQLite ne casse pas les endpoints existants ;
- que le backend reste simple à lancer sur Raspberry Pi ;
- que les fichiers .env et secrets ne sont pas exposés ;
- que /health et /api/status sont cohérents ;
- que les erreurs sont claires.

Donne uniquement les corrections prioritaires pour stabiliser le projet en moins d’une journée.
```

---

# Jour 2 — Robot réel, sonde simulée et capteurs mock

## Objectif du jour

Créer la couche robot/capteurs et faire bouger réellement le Adeept PiCar Pro avec un test matériel simple.

Le backend ne doit pas planter si le robot n’est pas connecté. Le mode `mock` doit rester disponible sur ordinateur.

## Tâches prioritaires

### 1. Créer l’abstraction robot

Créer :

```text
raspberry_pi/robot/base.py
raspberry_pi/robot/mock_controller.py
raspberry_pi/robot/adeept_controller.py
raspberry_pi/robot/probe_controller.py
```

Interface minimale :

```python
class RobotController:
    def forward(self, speed: int = 50): ...
    def backward(self, speed: int = 50): ...
    def turn_left(self, speed: int = 40, duration: float = 1.0): ...
    def turn_right(self, speed: int = 40, duration: float = 1.0): ...
    def stop(self): ...
    def move_to_point(self, x: float, y: float): ...
```

Le `MockRobotController` doit simplement logger les actions.

Le `AdeeptRobotController` doit encapsuler le code Adeept, mais ne doit pas faire planter tout le backend si les librairies matérielles ne sont pas disponibles.

### 2. Créer le test matériel

Créer :

```text
raspberry_pi/hardware_test.py
```

Ce script doit permettre de tester :

- avancer 1 seconde ;
- arrêter ;
- reculer 1 seconde ;
- arrêter ;
- tourner à gauche ;
- tourner à droite ;
- arrêter ;
- descendre/remonter la sonde ou tester un servo.

Le script doit être très simple, car il sera utilisé sur Raspberry Pi.

Exemple d’usage :

```bash
python raspberry_pi/hardware_test.py --test motors
python raspberry_pi/hardware_test.py --test servo
python raspberry_pi/hardware_test.py --test all
```

### 3. Créer la couche sonde

Créer `ProbeController` :

```python
class ProbeController:
    def lower_probe(self): ...
    def stabilize(self, seconds: int = 3): ...
    def raise_probe(self): ...
```

Au début, la sonde peut être :

- un vrai servo ;
- une tige montée sur servo ;
- ou un simple mouvement visible du robot si la sonde n’est pas encore montée.

### 4. Créer l’abstraction capteur

Créer :

```text
raspberry_pi/sensors/base.py
raspberry_pi/sensors/mock_sensor.py
raspberry_pi/sensors/real_sensor_placeholder.py
```

Interface :

```python
class SensorReader:
    def read(self) -> dict:
        ...
```

Le mock doit retourner des valeurs crédibles :

```json
{
  "ph": 6.7,
  "humidity": 43.0,
  "temperature": 24.5,
  "ec": 1.2
}
```

Plages recommandées :

```text
pH : 5.5 à 8.2
humidité : 20 à 75 %
température : 15 à 35 °C
EC : 0.4 à 3.0 mS/cm
```

### 5. Préparer l’intégration future des capteurs

Le fichier `real_sensor_placeholder.py` doit contenir une structure propre, mais peut lever une erreur claire :

```python
raise NotImplementedError("Real sensor integration is not implemented yet. Use SENSOR_MODE=mock.")
```

## Prompt Codex — Jour 2

```text
Crée une couche robot et capteurs propre pour préparer la démonstration sur Adeept PiCar Pro.

À ajouter :
- raspberry_pi/robot/base.py
- raspberry_pi/robot/mock_controller.py
- raspberry_pi/robot/adeept_controller.py
- raspberry_pi/robot/probe_controller.py
- raspberry_pi/sensors/base.py
- raspberry_pi/sensors/mock_sensor.py
- raspberry_pi/sensors/real_sensor_placeholder.py
- raspberry_pi/hardware_test.py

Contraintes :
- ROBOT_MODE=mock ou adeept
- SENSOR_MODE=mock ou real
- le mode mock doit marcher sur PC sans Raspberry Pi ;
- le mode adeept doit être tolérant si les librairies matérielles ne sont pas installées ;
- hardware_test.py doit permettre de tester moteurs, stop et servo ;
- ne modifie pas brutalement tout le backend ;
- documente comment tester le robot dans README.md.
```

## Contrôle à faire après Codex

Sur PC :

```bash
python raspberry_pi/hardware_test.py --test all
```

En mode mock, cela doit afficher des logs et ne pas planter.

Sur Raspberry Pi :

```bash
python raspberry_pi/hardware_test.py --test motors
python raspberry_pi/hardware_test.py --test servo
```

Il faut tester à vitesse faible au début.

Recommandation sécurité :

- poser le robot sur un support ou le tenir légèrement ;
- commencer avec faible vitesse ;
- garder une main proche de l’interrupteur ;
- vérifier que `stop()` fonctionne.

## Prompt Claude Code — Revue Jour 2

```text
Audite la couche robot/capteurs créée par Codex.

Vérifie :
- que le mode mock fonctionne hors Raspberry Pi ;
- que le mode adeept ne fait pas planter le backend si les librairies manquent ;
- que l’interface RobotController est claire ;
- que le script hardware_test.py est sûr ;
- que la future intégration capteur réel sera simple ;
- que la séparation robot / capteurs / backend est propre.

Donne les corrections prioritaires, en visant une démo dans moins de 48h.
```

---

# Jour 3 — Mission complète, frontend démo et répétition générale

## Objectif du jour

Réaliser la chaîne complète :

```text
Interface → Backend → MissionRunner → Robot → Sonde → Capteur mock → Backend → Recommandation → Interface → Chatbot
```

## Tâches prioritaires

### 1. Créer ou solidifier `mission_runner.py`

Le mission runner doit faire :

```text
1. charger une mission ;
2. passer l’état à MOVING ;
3. déplacer le robot vers le point ;
4. arrêter le robot ;
5. passer l’état à STABILIZING ;
6. descendre la sonde ;
7. attendre 3 secondes ;
8. lire le capteur mock ;
9. remonter la sonde ;
10. envoyer ou enregistrer la mesure ;
11. générer une recommandation ;
12. passer au point suivant ;
13. terminer la mission.
```

Statuts recommandés :

```text
IDLE
MISSION_LOADED
MOVING
STABILIZING
MEASURING
RECOMMENDING
DONE
ERROR
EMERGENCY_STOP
```

### 2. Ajouter arrêt d’urgence

Endpoint :

```text
POST /api/mission/stop
```

Effet obligatoire :

```text
robot.stop()
mission_status = EMERGENCY_STOP
```

Même si le reste est imparfait, l’arrêt d’urgence doit être fiable.

### 3. Ajouter bouton frontend si absent

Le frontend doit clairement avoir :

- bouton “Démarrer mission” ;
- bouton “Arrêt d’urgence” ;
- statut robot ;
- point actuel ;
- dernière mesure ;
- recommandation ;
- chatbot.

Ne pas refaire tout le design. Il faut juste rendre la démo claire.

### 4. Ajouter `start_demo.sh`

Créer un script de lancement simple :

```bash
#!/bin/bash
set -e

echo "Starting Agri-Botics demo..."

export HOST=0.0.0.0
export PORT=8000

python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Si le frontend est servi séparément :

```bash
cd frontend/frontend_real_backend
python3 -m http.server 5500
```

Mais idéalement, pour la démo, servir le frontend directement depuis FastAPI ou documenter deux terminaux.

### 5. Préparer le mode présentation

Prévoir deux modes :

```env
ROBOT_MODE=adeept
SENSOR_MODE=mock
LLM_PROVIDER=gemini
DEMO_MODE=true
```

Le jour de la soutenance :

```env
ROBOT_MODE=adeept
SENSOR_MODE=mock
LLM_PROVIDER=openai
DEMO_MODE=true
```

Si internet tombe :

```env
ROBOT_MODE=adeept
SENSOR_MODE=mock
LLM_PROVIDER=local
DEMO_MODE=true
```

Même si le mode local est simple, il doit permettre de répondre avec une phrase préprogrammée.

## Prompt Codex — Jour 3

```text
Maintenant intègre la chaîne complète de démonstration.

Objectif :
Interface → Backend → MissionRunner → RobotController → ProbeController → SensorReader mock → sauvegarde mesure → recommandation → retour interface.

À faire :
- créer ou améliorer raspberry_pi/mission_runner.py ;
- ajouter les statuts IDLE, MISSION_LOADED, MOVING, STABILIZING, MEASURING, RECOMMENDING, DONE, ERROR, EMERGENCY_STOP ;
- ajouter ou stabiliser POST /api/mission/start ;
- ajouter ou stabiliser POST /api/mission/stop ;
- garantir que /api/status reflète l’état courant ;
- s’assurer que robot.stop() est appelé en cas d’arrêt d’urgence ;
- utiliser SENSOR_MODE=mock pour produire les mesures ;
- ne pas refaire tout le frontend, mais ajouter/adapter les boutons nécessaires si besoin ;
- créer start_demo.sh ;
- documenter la démo dans README.md.

Priorité absolue :
La chaîne doit fonctionner en mode mock sur PC et être prête à passer en ROBOT_MODE=adeept sur Raspberry Pi.
```

## Contrôle à faire après Codex

### Test backend

```bash
python -m uvicorn backend.app:app --reload
```

Puis :

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/status
```

### Test mission

Depuis l’interface :

1. charger une mission de 2 ou 3 points ;
2. cliquer sur démarrer ;
3. vérifier que le statut change ;
4. vérifier qu’une mesure apparaît ;
5. vérifier qu’une recommandation apparaît ;
6. cliquer sur arrêt d’urgence ;
7. vérifier que le robot s’arrête ou que le mock logge bien `stop`.

### Test chatbot

Questions à tester :

```text
Pourquoi recommandes-tu cette culture ?
Explique-moi l’état du sol.
شنو خاصني ندير للتربة؟
واش هاد التربة مزيانة للطماطم؟
```

## Prompt Claude Code — Revue finale

```text
Fais une revue finale du projet pour une démonstration dans une foire/soutenance.

Vérifie :
- que la chaîne mission complète est cohérente ;
- que l’arrêt d’urgence fonctionne ;
- que le mode mock permet une démo sans capteurs ;
- que le passage ROBOT_MODE=mock vers ROBOT_MODE=adeept est clair ;
- que SENSOR_MODE=mock vers SENSOR_MODE=real sera simple plus tard ;
- que le README explique précisément comment lancer la démo ;
- que le projet reste défendable scientifiquement.

Donne une checklist finale et les corrections critiques seulement.
```

---

## 6. Répartition Codex / Claude Code

## Codex

Codex doit être utilisé comme **exécutant local**.

Lui demander :

- modifier les fichiers ;
- créer les modules ;
- ajouter endpoints ;
- exécuter tests ;
- corriger erreurs d’import ;
- ajouter SQLite ;
- écrire scripts ;
- brancher robot/capteurs ;
- mettre à jour README.

Codex est très utile quand il faut agir directement dans le dossier.

## Claude Code

Claude Code doit être utilisé comme **architecte/relecteur**.

Lui demander :

- auditer les changements ;
- repérer les incohérences ;
- vérifier la maintenabilité ;
- améliorer README ;
- préparer scénario de démo ;
- identifier risques ;
- proposer corrections prioritaires.

## Méthode de travail

Ne pas faire travailler Codex et Claude en même temps sur les mêmes fichiers.

Processus conseillé :

```text
1. Demander à Codex d’implémenter une étape.
2. Tester localement.
3. Demander à Claude Code d’auditer.
4. Corriger avec Codex.
5. Tester encore.
6. Passer à l’étape suivante.
```

---

## 7. Scénario de démonstration final

Le scénario doit être court, visuel et maîtrisé.

### Étape 1 — Lancement

Sur Raspberry Pi :

```bash
cd PLBD
source .venv/bin/activate
./start_demo.sh
```

Sur PC :

```text
http://IP_RASPBERRY:8000
```

ou :

```text
http://IP_RASPBERRY:5500
```

selon le choix frontend.

### Étape 2 — Présentation rapide

Dire :

> Voici Agri-Botics, un prototype de robot agricole intelligent capable de réaliser une mission de mesure sur plusieurs zones, d’analyser les paramètres du sol et de proposer une recommandation de culture ou de correction.

### Étape 3 — Mission

Actions :

1. définir 2 ou 3 points ;
2. lancer la mission ;
3. montrer le robot qui bouge ;
4. montrer l’arrêt au point ;
5. montrer la sonde qui descend ;
6. montrer la mesure ;
7. montrer la recommandation ;
8. poser une question au chatbot.

### Étape 4 — Chatbot

Questions de démonstration :

```text
Pourquoi recommandes-tu cette culture ?
Que faut-il corriger dans ce sol ?
Explique-moi la recommandation simplement.
شنو خاصني ندير للتربة؟
```

### Étape 5 — Conclusion

Dire :

> Le prototype fonctionne aujourd’hui en mode capteur simulé, car les capteurs réels ne sont pas encore disponibles. Mais l’architecture est prête : il suffira de remplacer le module `MockSensorReader` par `RealSensorReader` pour brancher la sonde réelle, sans modifier le backend, le moteur de recommandation ou l’interface.

---

## 8. Checklist finale avant la foire

## Matériel

- Raspberry Pi alimentée ;
- Adeept PiCar Pro chargé ;
- carte SD prête ;
- câble USB-C ou alimentation ;
- PC connecté au même Wi-Fi ;
- point d’accès mobile disponible ;
- servo/sonde factice montée ;
- batterie chargée ;
- souris/clavier si besoin ;
- écran HDMI de secours si possible.

## Logiciel

- backend démarre ;
- frontend accessible ;
- `.env` configuré ;
- `ROBOT_MODE=adeept` sur Raspberry ;
- `SENSOR_MODE=mock` ;
- `LLM_PROVIDER=gemini` ou `openai` ;
- SQLite créée ;
- `/health` fonctionne ;
- `/api/status` fonctionne ;
- mission testée ;
- arrêt urgence testé ;
- chatbot testé ;
- fallback testé.

## Démo

- scénario répété au moins 5 fois ;
- mission courte de 2 ou 3 points ;
- vitesse robot faible et contrôlée ;
- arrêt d’urgence connu ;
- phrase sur capteurs préparée ;
- questions chatbot préparées ;
- plan B prêt.

---

## 9. Plan B si quelque chose échoue

## Si le robot ne bouge pas

Présenter :

- interface ;
- mission mock ;
- descente sonde simulée dans les logs ;
- mesures et recommandations ;
- expliquer que la couche robot est isolée et que le test matériel est en cours.

## Si internet tombe

Utiliser :

```env
LLM_PROVIDER=local
```

ou désactiver la réponse LLM et utiliser une réponse locale simple :

> D’après les mesures disponibles, le système recommande cette culture car les paramètres du sol sont compatibles avec les plages agronomiques définies.

## Si le backend tombe

Relancer :

```bash
./start_demo.sh
```

Prévoir une capture ou vidéo courte de la démo réussie.

## Si les mesures ne s’affichent pas

Tester directement :

```bash
curl http://localhost:8000/api/status
```

Puis montrer la recommandation ou relancer la mission.

---

## 10. Livrables à produire

À la fin des 3 jours, le projet doit contenir :

- `README.md` propre ;
- `.env.example` ;
- `start_demo.sh` ;
- backend avec `/health` et `/api/status` ;
- SQLite ou persistance locale ;
- couche robot mock/adeept ;
- couche capteur mock/real placeholder ;
- script `hardware_test.py` ;
- mission runner ;
- arrêt d’urgence ;
- interface démo utilisable ;
- scénario de soutenance ;
- checklist de lancement.

---

## 11. Ordre réel d’exécution résumé

```text
Jour 1 matin :
- nettoyer secrets
- ajouter /health, /api/status
- ajouter SQLite

Jour 1 soir :
- tester backend + frontend
- revue Claude

Jour 2 matin :
- créer RobotController + Mock + Adeept
- créer SensorReader + Mock + Real placeholder

Jour 2 soir :
- tester hardware_test.py
- tester moteurs/servo sur Raspberry si possible
- revue Claude

Jour 3 matin :
- intégrer mission_runner
- connecter mission → robot → sonde → mesure mock → recommandation

Jour 3 après-midi :
- adapter frontend démo
- ajouter arrêt urgence
- ajouter start_demo.sh

Jour 3 soir :
- répétition générale
- correction bugs critiques
- préparer plan B
```

---

## 12. Formulation défendable du projet

À utiliser dans la soutenance :

> Notre solution est un prototype intégré d’aide à la décision agricole. Elle combine un robot mobile, une logique de mission par points, une acquisition de paramètres du sol, un moteur de recommandation agronomique, une interface web et un chatbot multilingue.  
>  
> La partie capteur est volontairement isolée. En l’absence temporaire de la sonde réelle, nous utilisons un mode mock contrôlé pour valider toute la chaîne fonctionnelle : déplacement, stabilisation, mesure, sauvegarde, recommandation et explication conversationnelle.  
>  
> Dès l’arrivée du capteur, il suffira d’implémenter le module de lecture réelle sans modifier le reste du système.

---

## 13. Priorité absolue

Si le temps devient très serré, se concentrer uniquement sur ces 5 choses :

```text
1. Backend stable + /health + /api/status
2. RobotController mock/adeept + hardware_test.py
3. SensorReader mock
4. Mission complète avec sonde simulée
5. Interface avec bouton start + arrêt urgence + affichage mesure/recommandation
```

Tout le reste est secondaire.
