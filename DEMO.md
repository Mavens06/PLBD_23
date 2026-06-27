# 🎬 Lancer une démo Agribotics — guide autonome

Ce guide explique comment **lancer tout le projet** et **obtenir un lien public**
pour faire une démo complète, de bout en bout, sans aide.

Il y a **deux façons** de démontrer :

| | A. Robot réel (Raspberry Pi) | B. Local sur PC (sans matériel) |
|---|---|---|
| Matériel | Pi + robot + sonde NEMA | Aucun (mode `mock`) |
| Lien | Public (tunnel internet) | `http://localhost:5500` |
| Pour | Présentation publique, vrai robot | Test / répétition rapide |

---

## A. Démo complète sur la Raspberry Pi (robot réel)

### 1. Se connecter à la Pi
```bash
ssh pi@172.22.6.144
```
> Si l'IP a changé : la trouver sur la box, ou `hostname -I` une fois connecté en écran/clavier.

### 2. Tout lancer en UNE commande
```bash
bash ~/demo.sh
```
Ça démarre :
- le **backend** (port 8000) — qui sert **aussi l'interface** (origine unique),
- le **robot** en mode surveillance (`--watch`, exécute les missions demandées depuis l'UI),
- le **tunnel public** (cloudflared),

puis affiche le **lien à partager** :
```
============================================================
  ✅ DÉMO AGRIBOTICS PRÊTE — lien à partager :

      https://xxxx-xxxx-xxxx.trycloudflare.com
============================================================
```

### 3. Ouvrir le lien
Colle l'URL dans **n'importe quel navigateur** (PC, téléphone). Tout passe par ce
seul lien : interface, données, chatbot vocal.

### 4. Revoir le lien plus tard / l'arrêter
```bash
bash ~/demo.sh --url     # réaffiche le lien courant
bash ~/demo.sh --stop    # arrête backend + robot + tunnel
```

> ⚠️ **Le lien change à chaque redémarrage du tunnel.** Relance `bash ~/demo.sh`
> et récupère la nouvelle URL. Garde le terminal/SSH ouvert pendant la démo
> (ou utilise l'auto-démarrage systemd, cf. plus bas).

---

## B. Démo locale sur PC (mode mock, sans matériel)

Depuis la racine du dépôt :
```bash
./start_demo.sh
```
Puis ouvre **http://localhost:5500**. Backend + robot simulé + interface, tout en
local. Idéal pour répéter la démo sans la Pi.

---

## 🧭 Déroulé d'une démo (ce qu'on montre)

1. **Onglet Carte / Plan** — définir les points de mesure (menus déroulants
   `0 / 1.8 / 3.6 m`), ou cliquer un preset (3 / 5 / 8 points). La carte s'adapte.
2. **▶ Démarrer mission** — le robot visite les points : à chaque arrêt, la
   **sonde NEMA descend** (9 s), mesure le sol (pH, humidité, température, EC),
   remonte, puis passe au point suivant. La progression se met à jour en direct.
3. **Onglet Terrain** — jauges des 4 variables + alerte salinité.
4. **Onglet Conseils** — top-3 cultures recommandées par zone (ML/règles) +
   corrections de sol + bulletin météo / consigne d'irrigation.
5. **Chatbot 🚜 (icône bas-droite)** — poser une question en FR / arabe / darija,
   à l'écrit **ou à la voix** (micro). Il répond avec le contexte du sol mesuré.

---

## ✅ Prérequis (déjà en place sur la Pi)

- **Connexion internet** : requise pour le tunnel public **et** le chatbot
  (le cœur métier ML/règles, lui, marche hors-ligne).
- **Clé API du chatbot** dans `~/PLBD/.env` (`GEMINI_API_KEY` ou clé OpenAI selon
  le fournisseur). Sans clé, l'app marche mais le chatbot retombe sur une réponse
  locale simplifiée.
- **Sonde NEMA** : pilotée par les GPIO de la Pi (`PROBE_NEMA_GPIO=1` dans `.env`,
  course 9 s @ 150 tr/min). Vérif moteur seul : `python3 ~/nema_test.py 2 120 H`.

---

## 🔁 Rappel des scripts (sur la Pi, dans `~`)

- `~/demo.sh` — **tout lancer + afficher le lien** (`--url`, `--stop`).
- `~/start_chain.sh` — backend (8000) + frontend (5500) + robot `--watch`.
- `~/start_tunnel.sh` — tunnel cloudflared sur le port 8000.
- Logs : `/tmp/backend.log`, `/tmp/robot.log`, `/tmp/cloudflared.log`.

## 🟢 Auto-démarrage au boot (optionnel, sans SSH)

Pour que la chaîne démarre seule à l'allumage de la Pi (services systemd) :
voir `deploy/README.md`. Pratique pour une borne de démo qu'on allume et c'est prêt
(le tunnel public reste à lancer/relire via `bash ~/demo.sh`).
