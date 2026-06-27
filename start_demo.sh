#!/usr/bin/env bash
#
# start_demo.sh — Lance toute la chaîne Agribotics en une commande.
#
#   Backend FastAPI (:8000)  +  robot en mode --watch (AUTONOME)  +  frontend (:5500)
#
# ── LANCEMENT AUTONOME ────────────────────────────────────────────────────────
#   Le robot tourne en mode `--watch` : il ATTEND qu'une mission soit demandée
#   depuis l'interface (bouton « Démarrer mission ») puis l'exécute TOUT SEUL
#   (déplacement → sonde → mesure → point suivant), sans intervention.
#
#   ./start_demo.sh                       # PC, sans matériel (APP_MODE=mock)
#   APP_MODE=hardware ./start_demo.sh     # robot réel (Raspberry Pi)
#
#   ⚠ Sur la Pi en production, le robot est DÉJÀ lancé en permanence par systemd
#     (deploy/install.sh). Inutile de lancer ce script : ouvre simplement le lien
#     (./deploy/link.sh) et démarre la mission depuis l'interface.
#
# ── DÉPLACEMENT LONGUE DISTANCE ───────────────────────────────────────────────
#   Par défaut le parcours physique est BORNÉ à un petit carré (mode démo,
#   ROBOT_MAX_FIELD_M ≈ 0.9 m). Pour parcourir les VRAIES distances du plan
#   (champ réel, échelle 1:1), active le mode longue distance :
#
#   LONG_DISTANCE=1 APP_MODE=hardware ./start_demo.sh
#       → ROBOT_WORLD_SCALE=1.0  (1 m du plan = 1 m au sol)
#       → ROBOT_MAX_FIELD_M=1000 (plus de bornage : le plan n'est pas réduit)
#
#   Sur la Pi en PERMANENCE (systemd), ajoute plutôt ces 2 lignes au .env :
#       ROBOT_WORLD_SCALE=1.0
#       ROBOT_MAX_FIELD_M=1000
#   puis :  sudo systemctl restart agribotics-robot
#   (Pense à caler ROBOT_SPEED_MPS sur la vitesse réelle : sans encodeurs, la
#    distance est temporisée — une vitesse juste = des distances justes.)
#
# Ctrl-C arrête proprement les trois processus.
#
set -euo pipefail

cd "$(dirname "$0")"

PY="$PWD/.venv/bin/python"   # chemin ABSOLU : reste valide après un `cd` (frontend)
APP_MODE="${APP_MODE:-mock}"
BACKEND_HOST="${HOST:-0.0.0.0}"
BACKEND_PORT="${PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5500}"

if [ ! -x "$PY" ]; then
  echo "‼ Environnement Python introuvable ($PY)."
  echo "  Crée-le : python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt"
  exit 1
fi

# Mode de déplacement : "long" (échelle réelle 1:1) ou "démo" (emprise bornée).
if [ "${LONG_DISTANCE:-0}" = "1" ] || [ "${DISTANCE:-}" = "long" ]; then
  export ROBOT_WORLD_SCALE="${ROBOT_WORLD_SCALE:-1.0}"
  export ROBOT_MAX_FIELD_M="${ROBOT_MAX_FIELD_M:-1000}"
  MOVE_DESC="LONGUE DISTANCE (échelle 1:1, vraies distances du plan)"
else
  MOVE_DESC="démo (emprise bornée à ROBOT_MAX_FIELD_M=${ROBOT_MAX_FIELD_M:-0.9} m)"
fi

echo "=== Agribotics — démarrage (APP_MODE=$APP_MODE) ==="
echo "  déplacement : $MOVE_DESC"

pids=()
cleanup() {
  echo ""
  echo "=== arrêt des processus… ==="
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# 1) Backend FastAPI
APP_MODE="$APP_MODE" "$PY" -m uvicorn backend.app:app \
  --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
pids+=($!)
echo "  [1/3] backend       → http://$BACKEND_HOST:$BACKEND_PORT  (docs: /docs)"

# Laisse le backend ouvrir le port avant de lancer le watcher robot.
sleep 2

# 2) Robot en mode daemon (exécute le plan quand l'interface le demande)
APP_MODE="$APP_MODE" "$PY" -m raspberry_pi.main --watch &
pids+=($!)
echo "  [2/3] robot --watch → en attente d'ordre de mission"

# 3) Frontend (version backend réel)
( cd frontend/frontend_real_backend && "$PY" -m http.server "$FRONTEND_PORT" >/dev/null 2>&1 ) &
pids+=($!)
echo "  [3/3] frontend      → http://localhost:$FRONTEND_PORT"

echo ""
echo "Prêt. Ouvre http://localhost:$FRONTEND_PORT — Ctrl-C pour tout arrêter."
wait
