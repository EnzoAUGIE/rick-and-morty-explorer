"""Données d'épisodes depuis TMDB (optionnel).

L'API Rick & Morty s'arrête à la saison 5 et ne fournit aucune image d'épisode.
Si la variable TMDB_API_KEY est définie (clé v3 gratuite sur themoviedb.org), on lit
la liste des saisons puis chaque saison (saison 0 exclue) : 1 + N requêtes.
Sans clé, ou si TMDB échoue, `listing()` renvoie ce qu'il a pu lire (au pire rien) et
le catalogue sert l'API R&M seule : la page ne casse jamais à cause de TMDB.

Réponses mises en cache sur disque (DiskCache « tmdb », 7 jours), réutilisées même
périmées si TMDB échoue ; un échec n'est jamais mis en cache.
La clé d'API ne doit jamais apparaître dans un log ni dans une clé de cache.
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from . import config
from .disk_cache import DiskCache

log = logging.getLogger("app.tmdb")
IMG_BASE = "https://image.tmdb.org/t/p/w500"
# Table fixe : %B dépend de la locale, et l'API R&M écrit « December 2, 2013 »
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")


@dataclass(frozen=True)
class TmdbEntry:
    """Un épisode tel que TMDB le décrit (brut, avant fusion dans le catalogue)."""
    season: int
    number: int
    name: str
    air_date: str        # au format R&M (« September 4, 2022 »), ou ""
    overview: str        # "" si absent
    still: str | None    # URL complète de l'image
    guests: list[str]    # guest_stars[].character bruts, non vides

    @property
    def code(self) -> str:
        return f"S{self.season:02d}E{self.number:02d}"


@dataclass(frozen=True)
class TmdbListing:
    entries: list[TmdbEntry]
    complete: bool  # False si la liste des saisons ou une saison a échoué


def rm_date(iso: Any) -> str:
    """'2022-09-04' -> 'September 4, 2022' ; absent ou invalide -> ''."""
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _entry(raw: Any, season: int) -> TmdbEntry | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("episode_number"), int):
        return None
    still = _text(raw.get("still_path"))
    stars = raw.get("guest_stars")
    characters = [_text(g.get("character")) for g in stars if isinstance(g, dict)] \
        if isinstance(stars, list) else []
    return TmdbEntry(
        season=season, number=raw["episode_number"], name=_text(raw.get("name")),
        air_date=rm_date(raw.get("air_date")), overview=_text(raw.get("overview")),
        still=IMG_BASE + still if still else None, guests=[c for c in characters if c])


class TmdbClient:
    def __init__(self, api_key: str | None = None, *,
                 show_id: int = config.TMDB_SHOW_ID,
                 transport: httpx.AsyncBaseTransport | None = None,
                 disk_ttl: int = config.DISK_CACHE_TTL_SECONDS) -> None:
        if api_key is None:  # lue à la construction, pas à l'import (tests, environnement)
            api_key = config.TMDB_API_KEY
        self.enabled = bool(api_key)
        self._key, self._show = api_key, show_id
        self._http = httpx.AsyncClient(base_url="https://api.themoviedb.org/3",
                                       timeout=8, transport=transport)
        self._disk = DiskCache("tmdb", disk_ttl)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get_json(self, path: str) -> dict | None:
        """Réponse JSON, depuis le cache si frais. None si TMDB échoue sans cache :
        l'appelant passe alors en mode dégradé."""
        key = f"{path}?language=fr-FR"  # jamais api_key : la clé n'entre pas dans le cache
        cached = self._disk.lookup(key)
        if cached and not isinstance(cached.data, dict):  # JSON valide mais inattendu
            cached = None
        if cached and cached.fresh:
            return cached.data
        try:
            r = await self._http.get(path, params={"api_key": self._key, "language": "fr-FR"})
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                raise ValueError("réponse inattendue")
        except (httpx.HTTPError, ValueError) as exc:
            # pas str(exc) : le message d'httpx contient l'URL, donc la clé api_key
            reason = (f"HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError)
                      else type(exc).__name__)
            if cached:
                log.warning("TMDB %s indisponible (%s) : réponse en cache (périmée) utilisée",
                            path, reason)
                return cached.data
            log.warning("TMDB %s indisponible (%s) : épisodes R&M seuls", path, reason)
            return None  # un échec n'est jamais stocké
        self._disk.store(key, data)
        return data

    async def listing(self) -> TmdbListing:
        """Épisodes des saisons 1 et plus. Ne lève jamais."""
        if not self.enabled:
            return TmdbListing([], complete=True)
        show = await self._get_json(f"/tv/{self._show}")
        if show is None:
            return TmdbListing([], complete=False)
        raw_seasons = show.get("seasons")
        numbers = sorted({s["season_number"] for s in raw_seasons
                          if isinstance(s, dict) and isinstance(s.get("season_number"), int)
                          and s["season_number"] >= 1}) if isinstance(raw_seasons, list) else []
        entries: list[TmdbEntry] = []
        complete = True
        for n in numbers:
            data = await self._get_json(f"/tv/{self._show}/season/{n}")
            if data is None:
                complete = False
                continue
            raw_episodes = data.get("episodes")
            entries += [e for e in (_entry(raw, n) for raw in raw_episodes) if e] \
                if isinstance(raw_episodes, list) else []
        return TmdbListing(entries, complete)
