#!/usr/bin/env bash
#
# tunnel.sh — Tunnel public cloudflared "quick" vers le backend local (:8000).
#
# Tourne en continu (lancé par agribotics-tunnel.service) et écrit l'URL publique
# dans .agribotics/tunnel_url.txt, lue ensuite par `deploy/link.sh`. L'URL d'un
# quick-tunnel change à chaque (re)démarrage du tunnel ; tant que ce service
# tourne, le lien reste stable.
#
set -uo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"
mkdir -p .agribotics
URLFILE=".agribotics/tunnel_url.txt"
: > "$URLFILE"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "‼ cloudflared introuvable. Installez-le (cf. deploy/README.md)." >&2
  exit 1
fi

# cloudflared imprime l'URL publique sur stderr ; on la capture à la volée.
cloudflared tunnel --no-autoupdate --url "http://localhost:${PORT}" 2>&1 |
while IFS= read -r line; do
  printf '%s\n' "$line"
  if [[ "$line" == *trycloudflare.com* ]]; then
    url="$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' <<<"$line" | head -1)"
    [[ -n "$url" ]] && printf '%s\n' "$url" > "$URLFILE"
  fi
done
