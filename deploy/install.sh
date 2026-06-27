#!/usr/bin/env bash
#
# install.sh — Installe Agribotics en services systemd PERMANENTS.
#
# Après cette commande (une seule fois), au démarrage de la machine/robot :
#   • backend FastAPI (:8000, qui sert AUSSI le frontend à /)   → permanent
#   • robot en mode --watch (exécute les missions)               → permanent
#   • tunnel public cloudflared                                  → permanent
# … tous redémarrés automatiquement en cas de crash ou de reboot.
#
# À chaque connexion ensuite, le seul geste est :  ./deploy/link.sh
#
# Usage :
#   sudo ./deploy/install.sh                  # robot réel (APP_MODE=hardware)
#   sudo APP_MODE=mock ./deploy/install.sh    # PC de dev (sans matériel)
#   sudo NO_TUNNEL=1 ./deploy/install.sh      # sans le service tunnel
#
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "‼ Lance avec sudo :  sudo ./deploy/install.sh" >&2
  exit 1
fi

# Repo + utilisateur réels (et non root, même sous sudo).
cd "$(dirname "$0")/.."
REPO="$(pwd)"
RUN_USER="${SUDO_USER:-$USER}"
PYBIN="$REPO/.venv/bin/python"
APP_MODE="${APP_MODE:-hardware}"
UNIT_DIR="/etc/systemd/system"

echo "=== Installation des services Agribotics ==="
echo "  utilisateur : $RUN_USER"
echo "  dépôt       : $REPO"
echo "  APP_MODE    : $APP_MODE"
echo ""

[[ -x "$PYBIN" ]] || { echo "‼ venv introuvable : $PYBIN"; echo "  Crée-le : python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt"; exit 1; }
chmod +x "$REPO/deploy/tunnel.sh" "$REPO/deploy/link.sh" 2>/dev/null || true

write_unit() {  # $1 = nom, $2 = contenu
  local name="$1"; shift
  printf '%s\n' "$1" > "$UNIT_DIR/$name"
  echo "  ✓ $UNIT_DIR/$name"
}

write_unit "agribotics-backend.service" "[Unit]
Description=Agribotics backend (FastAPI, sert aussi le frontend)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO
Environment=APP_MODE=$APP_MODE
ExecStart=$PYBIN -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target"

write_unit "agribotics-robot.service" "[Unit]
Description=Agribotics robot mission daemon (--watch)
After=agribotics-backend.service network-online.target
Wants=agribotics-backend.service

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO
Environment=APP_MODE=$APP_MODE
ExecStart=$PYBIN -m raspberry_pi.main --watch
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

SERVICES=("agribotics-backend.service" "agribotics-robot.service")

if [[ "${NO_TUNNEL:-0}" != "1" ]]; then
  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "  ⚠ cloudflared introuvable → service tunnel installé mais inactif."
    echo "    Installe-le puis : sudo systemctl start agribotics-tunnel"
  fi
  write_unit "agribotics-tunnel.service" "[Unit]
Description=Agribotics public tunnel (cloudflared quick tunnel)
After=agribotics-backend.service network-online.target
Wants=agribotics-backend.service network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO
ExecStart=$REPO/deploy/tunnel.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"
  SERVICES+=("agribotics-tunnel.service")
fi

echo ""
echo "=== Activation (démarrage au boot + maintenant) ==="
systemctl daemon-reload
for s in "${SERVICES[@]}"; do
  systemctl enable "$s" >/dev/null 2>&1 || true
  systemctl restart "$s"
  echo "  ✓ $s actif"
done

echo ""
echo "=== Terminé. ==="
echo "  Tout tourne en permanence et redémarre au boot."
echo "  À chaque connexion, génère le lien :   ./deploy/link.sh"
echo "  Logs en direct :                        journalctl -u agribotics-backend -f"
