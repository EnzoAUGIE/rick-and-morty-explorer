"""Catalogue des épisodes : fusion des sources, filtre et pagination en mémoire.

Les routers d'épisodes ne parlent qu'à ce module. Il est construit paresseusement,
à la première requête qui en a besoin (jamais au démarrage), puis gardé en mémoire.
Ordre du catalogue : tri par (saison, numéro).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .client import NotFoundError, RickMortyClient
from .models import Episode, Guest, Page
from .tmdb import TmdbClient, TmdbEntry

PAGE_SIZE = 20


@dataclass(frozen=True)
class Position:
    """Place d'un épisode dans l'ordre du catalogue."""
    index: int  # à partir de 1
    total: int
    previous: Episode | None
    next: Episode | None


@dataclass(frozen=True)
class _State:
    episodes: list[Episode]
    by_id: dict[int, Episode]
    built_at: float


def _complementary(entry: TmdbEntry) -> Episode:
    """Épisode complémentaire : id déterministe saison*100 + numéro (ADR-0001)."""
    return Episode(
        id=entry.season * 100 + entry.number, source="tmdb", episode=entry.code,
        name=entry.name or entry.code, air_date=entry.air_date, summary=entry.overview,
        image=entry.still, characters=[], guests=[Guest(name=g) for g in entry.guests])


class Catalogue:
    """Chaque méthode peut déclencher la construction ; `ApiUnavailableError` ne remonte
    que si R&M est injoignable et qu'aucune donnée R&M n'existe (mémoire ou cache)."""

    def __init__(self, client: RickMortyClient, tmdb: TmdbClient) -> None:
        self._client, self._tmdb = client, tmdb
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
        listing = await self._tmdb.listing()
        by_code = {e.code: e for e in listing.entries}
        episodes = [e.model_copy(update={"image": by_code[e.episode].still})
                    if e.episode in by_code and by_code[e.episode].still else e
                    for e in episodes]
        served = {e.episode for e in episodes}
        episodes += [_complementary(entry) for code, entry in by_code.items()
                     if code not in served and 1 <= entry.number <= 99]
        episodes.sort(key=lambda e: (e.season, e.number))
        return _State(episodes, {e.id: e for e in episodes}, time.monotonic())

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

    async def get(self, episode_id: int) -> Episode:
        """Lève NotFoundError si aucun épisode du catalogue n'a cet id."""
        try:
            return (await self._ensure()).by_id[episode_id]
        except KeyError:
            raise NotFoundError(f"/episode/{episode_id}") from None

    async def same_season(self, ep: Episode) -> list[Episode]:
        if not ep.season:
            return []
        return [e for e in (await self._ensure()).episodes if e.season == ep.season]

    async def locate(self, ep: Episode) -> Position:
        """Voisins et rang de l'épisode dans l'ordre du catalogue."""
        episodes = (await self._ensure()).episodes
        i = next(n for n, e in enumerate(episodes) if e.id == ep.id)
        return Position(index=i + 1, total=len(episodes),
                        previous=episodes[i - 1] if i > 0 else None,
                        next=episodes[i + 1] if i + 1 < len(episodes) else None)
