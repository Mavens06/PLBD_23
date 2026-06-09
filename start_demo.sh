#!/usr/bin/env bash
#
# start_demo.sh — Lance toute la chaîne Agribotics en une commande.
#
#   Backend FastAPI (:8000)  +  robot en mode --watch  +  frontend réel (:5500)
#
# Usage :
#   ./start_demo.sh                 # APP_MODE=mock (PC, sans matériel)
#   APP_MODE=hardware ./start_demo.sh   # sur la Raspberry Pi (robot réel)
#
# Ctrl-C arrête proprement les trois processus.
#
set -euo pipefail

cd "$(dirname "$0")"

PY=./.venv/bin/python
APP_MODE="${APP_MODE:-mock}"
BACKEND_HOST="${HOST:-0.0.0.0}"
BACKEND_PORT="${PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5500}"

if [ ! -x "$PY" ]; then
  echo "‼ Environnement Python introuvable ($PY)."
  echo "  Crée-le : python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt"
  exit 1
fi

echo "=== Agribotics — démarrage (APP_MODE=$APP_MODE) ==="

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
