"""Images d'épisodes depuis TMDB (optionnel).

L'API Rick & Morty ne fournit aucune image d'épisode. Si la variable
TMDB_API_KEY est définie (clé v3 gratuite sur themoviedb.org), on récupère
la capture officielle de chaque épisode : 1 requête par saison, mise en cache.
Sans clé, ou si TMDB échoue, on renvoie {} et l'app affiche une mosaïque
des personnages à la place : la page ne casse jamais à cause de TMDB.
"""
from __future__ import annotations

import logging

import httpx

from . import config

log = logging.getLogger("app.tmdb")
IMG_BASE = "https://image.tmdb.org/t/p/w500"


class TmdbClient:
    def __init__(self, api_key: str = config.TMDB_API_KEY, *,
                 show_id: int = config.TMDB_SHOW_ID,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.enabled = bool(api_key)
        self._key, self._show = api_key, show_id
        self._http = httpx.AsyncClient(base_url="https://api.themoviedb.org/3",
                                       timeout=8, transport=transport)
        self._seasons: dict[int, dict[int, str]] = {}

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _season(self, season: int) -> dict[int, str]:
        if season in self._seasons:
            return self._seasons[season]
        stills: dict[int, str] = {}
        try:
            r = await self._http.get(f"/tv/{self._show}/season/{season}",
                                     params={"api_key": self._key, "language": "fr-FR"})
            r.raise_for_status()
            for ep in r.json().get("episodes", []):
                if ep.get("still_path"):
                    stills[ep["episode_number"]] = IMG_BASE + ep["still_path"]
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("TMDB saison %s indisponible (%s) : mosaïque utilisée", season, exc)
            return {}  # non mis en cache -> on réessaiera plus tard
        self._seasons[season] = stills
        return stills

    async def stills(self, episodes) -> dict[int, str]:
        """{id de l'épisode dans l'API R&M: url de l'image} pour une liste d'épisodes."""
        if not self.enabled:
            return {}
        out: dict[int, str] = {}
        for season in sorted({e.season for e in episodes}):
            by_number = await self._season(season)
            out.update({e.id: by_number[e.number] for e in episodes
                        if e.season == season and e.number in by_number})
        return out
