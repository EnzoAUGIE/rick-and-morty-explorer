"""Catalogue des épisodes : fusion des sources, filtre et pagination en mémoire.

Les routers d'épisodes ne parlent qu'à ce module. Il est construit paresseusement,
à la première requête qui en a besoin (jamais au démarrage), puis gardé en mémoire.
Ordre du catalogue : tri par (saison, numéro).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .client import RickMortyClient
from .models import Episode, Page

PAGE_SIZE = 20


@dataclass(frozen=True)
class _State:
    episodes: list[Episode]
    built_at: float


class Catalogue:
    """Chaque méthode peut déclencher la construction ; `ApiUnavailableError` ne remonte
    que si R&M est injoignable et qu'aucune donnée R&M n'existe (mémoire ou cache)."""

    def __init__(self, client: RickMortyClient) -> None:
        self._client = client
        self._state: _State | None = None

    async def _ensure(self) -> _State:
        if self._state is None:
            self._state = await self._build()
        return self._state

    async def _build(self) -> _State:
        episodes: list[Episode] = []
        page = 1
        while True:
            data = await self._client.list("episode", page)
            episodes.extend(data.results)
            if not data.has_next:
                break
            page += 1
        episodes.sort(key=lambda e: (e.season, e.number))
        return _State(episodes, time.monotonic())

    async def list(self, page: int = 1, *, name: str = "",
                   season: int | None = None) -> Page[Episode]:
        """Une page (20 épisodes) du catalogue filtré par nom (« contient ») et saison."""
        needle = name.strip().casefold()
        found = [e for e in (await self._ensure()).episodes
                 if needle in e.name.casefold() and (season is None or e.season == season)]
        pages = -(-len(found) // PAGE_SIZE)
        start = (page - 1) * PAGE_SIZE
        return Page[Episode](
            info={"count": len(found), "pages": pages,
                  "next": f"?page={page + 1}" if page < pages else None,
                  "prev": f"?page={page - 1}" if 1 < page <= pages else None},
            results=found[start:start + PAGE_SIZE], current=page)

    async def seasons(self) -> list[int]:
        """Saisons présentes dans le catalogue, triées."""
        return sorted({e.season for e in (await self._ensure()).episodes})
