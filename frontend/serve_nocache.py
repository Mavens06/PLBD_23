#!/usr/bin/env python3
"""
serve_nocache.py — Serveur statique SANS cache pour la démo Agribotics.

Le `python -m http.server` standard laisse le navigateur mettre en cache le JS :
après une mise à jour du code, le navigateur garde l'ancienne version (par ex.
une URL backend obsolète) tant qu'on ne force pas un rechargement. Ce serveur
ajoute des en-têtes anti-cache pour que la page serve toujours la dernière
version — indispensable quand on itère pendant les essais.

Usage :
    python3 serve_nocache.py [PORT] [DIR]
    # défaut : port 5500, dossier frontend_real_backend (relatif à ce fichier)
"""

from __future__ import annotations

import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler


class _NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5500
    directory = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "frontend_real_backend")
    os.chdir(directory)
    print(f"[serve_nocache] {directory} → http://0.0.0.0:{port} (anti-cache)", flush=True)
    HTTPServer(("0.0.0.0", port), _NoCacheHandler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
