"""Cache disque de réponses JSON (survit au redémarrage), partagé par les clients.

Un dossier par espace de noms : `config.CACHE_DIR / namespace`. Format d'un fichier
`<sha256 de la clé>.json` : `{"at": <epoch>, "data": ...}`.

Invariant de sécurité : la clé passée par l'appelant ne doit jamais contenir de secret
(clé d'API, jeton). Le module ne le vérifie pas : c'est la charge des appelants.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config

log = logging.getLogger("app.cache")


@dataclass(frozen=True)
class CacheHit:
    data: Any
    fresh: bool  # 0 <= âge < ttl ; un âge négatif (horloge reculée) compte comme périmé


class DiskCache:
    def __init__(self, namespace: str, ttl: int) -> None:
        self._namespace, self._ttl = namespace, ttl

    def _path(self, key: str) -> Path:
        # résolu à chaque appel : les tests remplacent config.CACHE_DIR
        return config.CACHE_DIR / self._namespace / f"{hashlib.sha256(key.encode()).hexdigest()}.json"

    def lookup(self, key: str) -> CacheHit | None:
        """None si absent ou illisible."""
        try:
            entry = json.loads(self._path(key).read_text(encoding="utf-8"))
            age = time.time() - float(entry["at"])
            return CacheHit(entry["data"], fresh=0 <= age < self._ttl)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def store(self, key: str, data: Any) -> None:
        """Écriture atomique (fichier temporaire + rename) ; un échec n'est jamais fatal."""
        path = self._path(key)
        tmp = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"at": time.time(), "data": data}, f)
            os.replace(tmp, path)
        except (OSError, TypeError, ValueError) as exc:
            log.warning("cache disque non écrit (%s)", type(exc).__name__)
            if tmp:
                Path(tmp).unlink(missing_ok=True)
