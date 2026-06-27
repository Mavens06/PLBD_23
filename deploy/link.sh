#!/usr/bin/env bash
#
# link.sh — Affiche (ou régénère) le lien public du robot Agribotics.
#
#   ./deploy/link.sh          → affiche le lien public actuel
#   ./deploy/link.sh --new    → régénère un NOUVEAU lien (redémarre le tunnel)
#
# C'est l'unique geste à faire à chaque connexion : le backend, le robot et le
# tunnel tournent déjà en permanence (services systemd). Voir deploy/README.md.
#
set -uo pipefail
cd "$(dirname "$0")/.."

URLFILE=".agribotics/tunnel_url.txt"

if [[ "${1:-}" == "--new" || "${1:-}" == "-n" ]]; then
  echo "↻ Régénération du lien (redémarrage du tunnel)…"
  sudo systemctl restart agribotics-tunnel.service
  : > "$URLFILE" 2>/dev/null || true
fi

# Attend l'apparition de l'URL (le tunnel met quelques secondes à s'établir).
for _ in $(seq 1 60); do
  if [[ -s "$URLFILE" ]]; then
    url="$(cat "$URLFILE")"
    echo ""
    echo "  🔗  Lien du robot :  $url"
    echo ""
    echo "  (ouvre ce lien sur ton téléphone — l'app et l'assistant Karim sont prêts)"
    echo ""
    exit 0
  fi
  sleep 0.5
done

echo "‼ Lien indisponible." >&2
echo "  Vérifie le service :  systemctl status agribotics-tunnel.service" >&2
echo "  (cloudflared est-il installé ? cf. deploy/README.md)" >&2
exit 1
