"""
offline_buffer.py — File d'attente locale des mesures non transmises.

Problème terrain : un robot au champ peut avoir un réseau instable. Si le push
HTTP vers le backend échoue, la mesure ne doit PAS être perdue. On l'écrit sur
le disque du robot (JSON Lines) et on la repousse au prochain essai.

Garanties :
  • Aucune perte : une mesure dont le push échoue est persistée immédiatement.
  • Idempotence simple : le flush ne supprime du fichier que les mesures
    effectivement re-transmises ; les échecs restent en file pour plus tard.
  • Robustesse : un fichier corrompu (ligne illisible) n'empêche pas le reste
    de fonctionner ; la ligne fautive est ignorée.

Format : une mesure = une ligne JSON dans le fichier `AGRIBOTICS_ROBOT_OUTBOX`
(défaut `.agribotics/robot_outbox.jsonl`).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, List


def default_outbox_path() -> Path:
    return Path(os.getenv("AGRIBOTICS_ROBOT_OUTBOX", ".agribotics/robot_outbox.jsonl"))


class OfflineBuffer:
    """File d'attente disque des mesures à (re)transmettre."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_outbox_path()

    # -- lecture / écriture bas niveau -------------------------------------
    def _read_all(self) -> List[dict]:
        if not self.path.exists():
            return []
        items: List[dict] = []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Ligne corrompue : on l'ignore sans casser le reste.
                        continue
        except OSError:
            return []
        return items

    def _write_all(self, items: List[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)        # remplacement atomique

    # -- API ----------------------------------------------------------------
    def pending(self) -> int:
        return len(self._read_all())

    def enqueue(self, payload: dict) -> None:
        """Ajoute une mesure non transmise à la file (append, sans tout relire)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def flush(self, push_fn: Callable[[dict], bool]) -> int:
        """
        Tente de retransmettre toutes les mesures en attente via `push_fn`.

        `push_fn(payload)` doit renvoyer True si la mesure est acceptée par le
        backend. Les mesures transmises sont retirées du fichier ; les échecs y
        restent pour un prochain flush. Renvoie le nombre de mesures transmises.
        """
        items = self._read_all()
        if not items:
            return 0
        remaining: List[dict] = []
        sent = 0
        stop = False
        for it in items:
            if stop:
                remaining.append(it)
                continue
            try:
                ok = push_fn(it)
            except Exception:
                ok = False
            if ok:
                sent += 1
            else:
                # Premier échec → backend probablement injoignable : on garde le
                # reste en file sans marteler le réseau.
                remaining.append(it)
                stop = True
        self._write_all(remaining)
        return sent
