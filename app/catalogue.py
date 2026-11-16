"""Catalogue des épisodes : fusion des sources, filtre et pagination en mémoire.

Les routers d'épisodes ne parlent qu'à ce module. Il est construit paresseusement,
à la première requête qui en a besoin (jamais au démarrage), puis gardé en mémoire.
Ordre du catalogue : tri par (saison, numéro).
"""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass

from .client import ApiUnavailableError, NotFoundError, RickMortyClient
from .models import Episode, Guest, Page
from .tmdb import TmdbClient, TmdbEntry

PAGE_SIZE = 20
# Liste fermée : « Aqua (Rick) » est un vrai nom de personnage, on ne retire pas toute parenthèse
CREDIT_NOTES = re.compile(r"\((?:voice|uncredited|archive footage|credit only)\)", re.I)


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _fold(text: str) -> str:
    """Forme de comparaison : sans accents, sans casse, espaces fusionnés."""
    return " ".join(_strip_accents(text).casefold().split())


def _split_guests(raw: list[str]) -> list[str]:
    """Noms de personnages : mentions de crédit retirées, « A / B » séparé, doublons supprimés."""
    names: dict[str, str] = {}
    for entry in raw:
        for part in CREDIT_NOTES.sub("", entry).split("/"):
            name = " ".join(part.split())
            if name:
                names.setdefault(_fold(name), name)
    return list(names.values())


class EpisodeMoved(Exception):
    """L'id demandé était celui d'un épisode complémentaire que R&M sert désormais."""

    def __init__(self, episode_id: int) -> None:
        super().__init__(episode_id)
        self.episode_id = episode_id  # id R&M vers lequel rediriger en 301


def _code_of(episode_id: int) -> str | None:
    """Code SxxEyy encodé par un id déterministe (saison*100 + numéro), ou None."""
    season, number = divmod(episode_id, 100)
    return f"S{season:02d}E{number:02d}" if season >= 1 and number >= 1 else None


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
    rm_by_code: dict[str, Episode]
    built_at: float


def _complementary(entry: TmdbEntry) -> Episode:
    """Épisode complémentaire : id déterministe saison*100 + numéro (ADR-0001)."""
    return Episode(
        id=entry.season * 100 + entry.number, source="tmdb", episode=entry.code,
        name=entry.name or entry.code, air_date=entry.air_date, summary=entry.overview,
        image=entry.still, characters=[], guests=[Guest(name=g) for g in _split_guests(entry.guests)])


class Catalogue:
    """Chaque méthode peut déclencher la construction ; `ApiUnavailableError` ne remonte
    que si R&M est injoignable et qu'aucune donnée R&M n'existe (mémoire ou cache)."""

    def __init__(self, client: RickMortyClient, tmdb: TmdbClient) -> None:
        self._client, self._tmdb = client, tmdb
        self._state: _State | None = None
        self._character_ids: dict[str, int | None] = {}  # nom plié -> fiche (None : aucune)

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
        return _State(episodes, {e.id: e for e in episodes},
                      {e.episode: e for e in episodes if e.source == "rm"}, time.monotonic())

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
        """Lève NotFoundError (inconnu) ou EpisodeMoved (code désormais servi par R&M)."""
        state = await self._ensure()
        if episode_id in state.by_id:
            return await self._with_linked_guests(state.by_id[episode_id])
        code = _code_of(episode_id)
        if code in state.rm_by_code:
            raise EpisodeMoved(state.rm_by_code[code].id)
        raise NotFoundError(f"/episode/{episode_id}")

    async def _with_linked_guests(self, ep: Episode) -> Episode:
        """Lie les invités d'un épisode complémentaire à leur fiche, une requête par nom au plus.

        Les requêtes sont séquentielles (429). Si R&M ne répond pas, les noms restants restent
        en texte simple et ne sont pas mémorisés : un prochain appel réessaie.
        """
        if ep.source != "tmdb":
            return ep
        guests: list[Guest] = []
        available = True
        for g in ep.guests:
            key = _fold(g.name)
            if key not in self._character_ids and available:
                try:
                    self._character_ids[key] = await self._find_character(g.name)
                except ApiUnavailableError:
                    available = False
            guests.append(Guest(name=g.name, character_id=self._character_ids.get(key)))
        return ep.model_copy(update={"guests": guests})

    async def _find_character(self, name: str) -> int | None:
        """Fiche au nom exact (accents et casse ignorés) sur la page 1 de la recherche ;
        en cas d'homonymes, l'id le plus bas."""
        page = await self._client.list("character", 1, name=_strip_accents(name))
        ids = [c.id for c in page.results if _fold(c.name) == _fold(name)]
        return min(ids) if ids else None

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
