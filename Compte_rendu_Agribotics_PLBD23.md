# Compte-rendu de travail — Projet Agri-Botics / PLBD_23

## But du document
Ce document résume proprement tout le travail mené jusqu’ici, les décisions prises, les idées retenues, l’architecture cible, ce qui a été modifié dans le repo, les points encore à corriger, et les prochaines pistes à suivre.

> **Note de lecture** : les sections 1 à 24 sont l'historique de conception. La **section 0 ci-dessous (état au 2026-05-29)** fait foi pour l'état *réel actuel* du code et prime en cas de divergence.

## 0. Mise à jour — État réel au 2026-05-29

Cette section reflète le code effectivement présent dans le dépôt à cette date.

### 0.1 Pipeline ML — TERMINÉ et raccordé
- Dataset synthétique régénéré : `ml_model/data/final_dataset.csv`, **10 000 lignes / 10 classes équilibrées**, 4 features `[ph, humidity, temperature, ec]` (aucun N/P/K, aucun rainfall).
- `train.py` : 4 modèles candidats (RandomForest, SVC RBF, GradientBoosting, LogReg) + **CV StratifiedKFold k=5**, sélection par F1-macro. **Gradient Boosting retenu.**
- Métrique de référence = **top-3 ≈ 0.91** (l'API expose un top-3, pas une culture unique). Le top-1 ≈ 0.57 est plafonné par le chevauchement agronomique des plages (borne de Bayes à 4 variables, pas un défaut).
- `predict.py` **raccordé au backend** : `engine="ml"` si `best_model.pkl`+`scaler.pkl` présents, sinon bascule automatique sur le moteur de règles (`engine="rules"`). Aucune exception. → **le point §16/§18 « inférence non raccordée » est RÉSOLU.**
- Vérification de réalisme effectuée : sensibilité correcte au pH (sol pH 7 → Vigne/Blé/Orge ; pH 8 → Betterave/Orge/Olivier), 8/10 cultures retrouvées dans leur propre top-3, identification forte sur sols distinctifs (sol oléicole → Olivier 98.9). Plages d'Olivier/Vigne analysées : **laissées telles quelles** (volontairement larges, fidèles à la littérature).

### 0.2 Chatbot — migré d'Ollama (local) vers **Gemini** (cloud)
- Motivation : Ollama/Qwen mobilisait ~2-5 Go de RAM en local. **Gemini Flash** est plus performant et ne consomme aucune RAM locale.
- `backend/chatbot_llm.py` : appel REST async à l'API **Google AI Studio** (`generateContent`). Config via `.env` : `GEMINI_API_KEY`, `GEMINI_MODEL` (défaut `gemini-2.0-flash`), `GEMINI_TIMEOUT`.
- **Conséquence d'architecture** : l'inférence ML/règles reste **100 % locale**, mais la couche conversationnelle (`/api/chat`) appelle désormais le cloud → connexion internet + clé API requises pour le chat uniquement.
- La logique de prompt (interdiction N/P/K, 10 cultures cibles, langue FR/AR/Darija) est inchangée.

### 0.3 Nouveauté — diagnostic de **correction du sol**
Répond à la question inverse de la recommandation : « j'ai choisi CETTE culture sur cette zone, comment corriger mon sol ? »
- Module `ml_model/rules/correction.py` : `diagnose(mesure, culture_cible)` → statut par variable (ok/trop bas/trop haut) + **action concrète déterministe** (chaux/dolomie pour relever le pH, soufre pour l'abaisser, irrigation, drainage, lessivage…) + compatibilité globale + **cultures naturellement mieux adaptées** au sol en l'état.
- Route `GET /api/recommendation/{point}/correction?crop=X`.
- Injecté dans le prompt du chatbot quand une culture cible est choisie : Gemini **reformule** les corrections sans en inventer (fidèle au principe « le LLM ne fait que mettre en forme »).

### 0.4 Arborescence réelle (≠ §11 historique)
Le code actif est **à la racine** (`backend/`, `ml_model/`, `raspberry_pi/`, `frontend/`). Le backend est **mono-fichier `app.py`** (pas de `models/routes/services/` séparés — refactor non nécessaire à ce stade). Deux frontends parallèles : `frontend/frontend_simulation/` (autonome, port 5501) et `frontend/frontend_real_backend/` (consomme l'API, port 5500). La doc technique de référence à jour est **`CLAUDE.md`**.

### 0.5 Reste à faire (à jour)
- Drivers matériels réels Raspberry Pi (`motors.py`, `navigation.py`, `safety.py`) — actuellement stubs.
- Persistance SQLite côté robot, météo Open-Meteo, polling live frontend, tests pytest.
- Régénérer les pickles ML sur chaque machine (`python ml_model/train.py`) — ils sont gitignorés.

## 1. Contexte général
Le projet est un prototype académique réel de robot agricole mobile.  
Le robot doit :
- se déplacer sur une parcelle,
- s’arrêter à des points de mesure prédéfinis,
- insérer une sonde dans le sol,
- mesurer 4 capteurs réels :
  - humidité,
  - pH,
  - conductivité / salinité,
  - température,
- produire une cartographie dynamique du sol,
- générer des recommandations utiles,
- proposer un chatbot vocal / textuel en français, arabe et darija marocaine.

## 2. Vision finale retenue
Le projet ne doit pas être une accumulation de modules décoratifs.  
La vision retenue est la suivante :
- un robot réel,
- des mesures réelles,
- une carte dynamique lisible,
- des recommandations simples et crédibles,
- une interface claire,
- un chatbot d’accessibilité.

## 3. Décisions techniques validées
- Raspberry Pi = cerveau principal du système.
- ESP32 abandonné dans l’architecture retenue.
- NPK retiré du cœur du prototype.
- Les 4 capteurs réellement assumés sont :
  - pH,
  - humidité,
  - température,
  - conductivité / salinité.
- Le chatbot reformule les résultats du système, il ne remplace pas la logique métier.

## 4. Fonctionnement retenu du robot
1. Démarrage d’une mission.
2. Déplacement entre des points de mesure fixes.
3. Arrêt sur un point.
4. Insertion de la sonde.
5. Stabilisation.
6. Plusieurs lectures.
7. Calcul d’une valeur finale robuste.
8. Mise à jour de la carte et des recommandations.
9. Passage au point suivant.

## 5. Protocole de mesure retenu
- Stabilisation : 3 à 5 secondes.
- Nombre de lectures : environ 10.
- Agrégation : moyenne propre ou médiane robuste.
- Métadonnées utiles : timestamp, dispersion, indicateur de qualité.

## 6. Cartographie retenue
- Carte légère, compréhensible, dynamique.
- Variables affichées :
  - humidité,
  - pH,
  - conductivité,
  - température.
- Le robot doit être visible sur le point actif.
- Clic sur zone = détail court.

## 7. Recommandations retenues
Approche V1 :
- règles métier simples,
- top actions prioritaires,
- classement de cultures.

## 8. Cultures retenues pour la V1
> ⚠️ **Liste corrigée (cf. §0)** — la liste réellement implémentée dans `ml_model/rules/crop_catalog.py` et le frontend est :
- Blé
- Tomate
- Oignon
- Carotte
- Pomme de terre
- Orge
- Betterave à sucre
- Olivier
- Vigne
- Pastèque

<sub>(ancienne liste de brainstorming, non retenue : Maïs, Agrumes, Luzerne, Pois chiche.)</sub>

## 9. Chatbot multilingue
Le chatbot doit :
- accepter texte + micro,
- répondre en français / arabe / darija,
- répondre à partir des vraies données du système,
- servir à l’accessibilité agriculteur.

## 10. Travail effectué sur l’architecture
- backend modulaire FastAPI consolidé,
- frontend conservé mais allégé,
- Raspberry Pi structurée en `robot / sensors / storage`,
- pipeline ML léger conservé,
- README réécrit.

## 11. Structure retenue du repo
```text
PLBD_23/
├── backend/
│   ├── app.py
│   ├── chatbot_llm.py
│   ├── models/
│   ├── routes/
│   └── services/
├── frontend/
│   ├── agribotics_v5.html
│   ├── css/
│   └── js/
├── ml_model/
│   ├── data/
│   ├── inference/
│   ├── rules/
│   └── train.py
├── raspberry_pi/
│   ├── main.py
│   ├── robot/
│   ├── sensors/
│   └── storage/
├── README.md
├── requirements.txt
└── .gitignore
```

## 12. Travail effectué sur le frontend
Contrainte forte retenue :
- garder le style visuel existant,
- alléger fortement le contenu.

Choix retenus :
- suppression de NPK dans l’interface,
- recentrage sur 4 espaces :
  - Terrain,
  - Carte,
  - Conseils,
  - Technique.

## 13. Interface retenue après simplification
- **Terrain** : mission, point actif, 4 capteurs, chatbot.
- **Carte** : carte + variable + détail court.
- **Conseils** : top actions, top cultures, météo utile.
- **Technique** : historique léger, qualité acquisition, logs essentiels.

## 14. Travail effectué sur le backend
- routes : mission, measurements, map, recommendations, weather, chat.
- schémas Pydantic clarifiés.
- séparation route / service / modèle retenue.

## 15. Travail effectué sur la Raspberry Pi
- `robot/`
- `sensors/`
- `storage/`
- acquisition_manager pour la logique robuste de lecture,
- stockage local via SQLite / session logger.

## 16. Travail effectué sur la partie ML
- `train.py` existe,
- `preprocess.py` existe,
- moteur de règles existe,
- couche d’inférence existe.

> ✅ **À JOUR (cf. §0.1)** : l'inférence modèle est **désormais entièrement raccordée** au backend (`predict.py` → `/api/recommendation`), avec fallback règles automatique. Le modèle est entraîné (Gradient Boosting, top-3 ≈ 0.91). Une couche de correction du sol a été ajoutée (§0.3).

## 17. Vérifications déjà faites sur le repo GitHub
- structure globale cohérente,
- README propre,
- frontend allégé,
- NPK retiré du périmètre principal,
- chatbot frontend basé sur 4 capteurs,
- principaux doublons retirés.

## 18. Points encore à corriger
> ✅ La plupart de ces points sont **traités** (cf. §0) — barrés ci-dessous :
- corriger l’emoji cassé de “Pomme de terre” *(à vérifier côté frontend)*,
- ~~raccorder la vraie inférence modèle~~ ✅ fait (§0.1),
- ~~harmoniser les noms de features~~ ✅ fait (`FEATURE_ORDER` partagé, mapping `ec↔salinity`),
- ~~vérifier le dataset final avant entraînement~~ ✅ fait (périmètre 4 vars vérifié, N/P/K/rainfall interdits),
- ~~faire remonter les recommandations depuis la couche ML/règles vers le backend~~ ✅ fait (§0.1).

## 19. Schéma de données ML à harmoniser
> ✅ **Résolu (cf. §0.1)**. Schéma final retenu = **4 variables uniquement** : `ph, humidity, temperature, ec`. Le `rainfall` envisagé ici a été **abandonné** (hors périmètre du capteur 4-en-1). Le mapping `temp→temperature` et `ec→salinity` est implémenté.

Runtime actuel :
- humidity
- ph
- ec
- temp

~~Schéma ML recommandé (avec rainfall)~~ — abandonné. Mapping conservé :
- `temp -> temperature`
- `ec -> salinity`

## 20. Approches externes envisagées
Des repos externes ont été envisagés pour l’inspiration :
- architecture robot,
- organisation capteurs / services,
- dashboard agricole,
- briques arabe / darija / voix.

Conclusion retenue :
- ne pas fusionner des repos entiers,
- seulement reprendre des idées de structure et quelques briques isolées.

## 21. Ce qu’il faut retenir absolument
- Le projet doit rester simple, crédible et défendable.
- La V1 doit montrer : robot réel + 4 capteurs + carte + recommandations + chatbot accessible.
- Raspberry Pi = cerveau principal.
- NPK ne fait plus partie du cœur du prototype.
- Le style de l’interface doit rester, mais avec moins de surcharge.
- Le ML doit être cohérent avant d’être sophistiqué.

## 22. Prochain ordre de travail recommandé
1. Corriger les dernières incohérences.
2. Vérifier le dataset final.
3. Lancer l’entraînement du modèle.
4. Brancher l’inférence dans le backend de recommandations.
5. Tester le flux complet en local.
6. Avancer ensuite sur l’intégration matérielle réelle.

## 23. Pistes à envisager ensuite
- drivers matériels réels,
- météo temps réel,
- historique multi-session,
- calibration terrain,
- amélioration progressive de la couche darija / voix.

## 24. Conclusion générale
Le travail mené ensemble a permis de transformer une idée large en une V1 structurée, cohérente et plus réaliste.  
La suite consiste surtout à :
- finaliser les raccords,
- valider les données,
- entraîner correctement le modèle,
- puis avancer vers l’intégration réelle.