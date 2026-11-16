"""Client de l'API Rick & Morty (équivalent amélioré de ClientHttp.java).

- asynchrone (httpx) ;
- cache mémoire (1 h) puis cache disque (DiskCache « api » : .cache/api, 7 jours, survit
  au redémarrage), réutilisés même périmés si l'API tombe ;
- nouvelles tentatives avec attente croissante sur 429 / 5xx / timeout
  (respecte l'en-tête Retry-After) ;
- récupération groupée (/character/1,2,3) : 1 requête au lieu de N.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel

from . import config
from .disk_cache import DiskCache
from .models import Character, Episode, Location, Page

log = logging.getLogger("app.client")

RESOURCES: dict[str, type[BaseModel]] = {
    "character": Character,
    "location": Location,
    "episode": Episode,
}
RETRY_STATUS = {429, 500, 502, 503, 504}


class NotFoundError(Exception):
    """La ressource demandée n'existe pas (404 de l'API ou recherche vide)."""


class ApiUnavailableError(Exception):
    """L'API ne répond pas après plusieurs essais (réseau, timeout, 429, 5xx)."""


class RickMortyClient:
    def __init__(
        self,
        base_url: str = config.API_BASE_URL,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        ttl: int = config.CACHE_TTL_SECONDS,
        disk_ttl: int = config.DISK_CACHE_TTL_SECONDS,
        retries: int = config.API_RETRIES,
        backoff: float = config.API_BACKOFF,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url, timeout=config.HTTP_TIMEOUT, transport=transport,
            headers={"User-Agent": "rickmorty-py (student project)"},
        )
        self._ttl = ttl
        self._disk = DiskCache("api", disk_ttl)
        self._retries, self._backoff = retries, backoff
        self._cache: dict[str, tuple[float, Any]] = {}

    async def aclose(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------ réseau
    async def _request(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET avec nouvelles tentatives. Renvoie la réponse finale (2xx ou 4xx définitif)."""
        delay = self._backoff
        reason = ""
        for attempt in range(self._retries + 1):
            try:
                resp = await self._http.get(url, params=params)
                if resp.status_code not in RETRY_STATUS:
                    return resp
                reason = f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("retry-after", "")
                wait = float(retry_after) if retry_after.isdigit() else delay
            except httpx.TransportError as exc:  # timeout, connexion refusée/coupée…
                reason = type(exc).__name__
                wait = delay
            if attempt < self._retries:
                log.warning("API %s -> %s, nouvel essai %d/%d dans %.1fs",
                            url, reason, attempt + 1, self._retries, wait)
                await asyncio.sleep(min(wait, 10))
                delay *= 2
        log.error("API %s -> %s, abandon après %d essais", url, reason, self._retries + 1)
        raise ApiUnavailableError(reason)

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        key = f"{path}?{sorted(params.items())}"
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < self._ttl:
            return hit[1]
        on_disk = self._disk.lookup(key)
        if on_disk and on_disk.fresh:
            self._cache[key] = (time.monotonic(), on_disk.data)
            return on_disk.data
        stale = hit[1] if hit else on_disk.data if on_disk else None

        try:
            resp = await self._request(path, params)
        except ApiUnavailableError:
            if stale is not None:  # mieux vaut une donnée un peu ancienne qu'une page d'erreur
                log.warning("API indisponible, réponse en cache (périmée) utilisée pour %s", key)
                return stale
            raise
        if resp.status_code == 404:
            raise NotFoundError(path)
        if resp.status_code >= 400:
            raise ApiUnavailableError(f"HTTP {resp.status_code}")

        data = resp.json()
        self._cache[key] = (time.monotonic(), data)
        self._disk.store(key, data)
        return data

    async def get_bytes(self, url: str) -> bytes:
        """Télécharge un fichier binaire (avatar) avec les mêmes nouvelles tentatives."""
        resp = await self._request(url)
        if resp.status_code == 404:
            raise NotFoundError(url)
        if resp.status_code >= 400:
            raise ApiUnavailableError(f"HTTP {resp.status_code}")
        return resp.content

    # ------------------------------------------------------------------ haut niveau
    async def list(self, resource: str, page: int = 1, **filters: Any) -> Page:
        """Une page de la liste, avec filtres optionnels (name, status, ...)."""
        model = RESOURCES[resource]
        try:
            data = await self._get_json(f"/{resource}", {"page": page, **filters})
        except NotFoundError:  # l'API renvoie 404 quand une recherche est vide
            return Page[model](info={"count": 0, "pages": 0}, results=[], current=page)
        return Page[model](**data, current=page)

    async def get(self, resource: str, item_id: int) -> BaseModel:
        model = RESOURCES[resource]
        return model(**await self._get_json(f"/{resource}/{item_id}"))

    async def get_many(self, resource: str, ids: list[int]) -> list[BaseModel]:
        """Plusieurs éléments en UNE requête : /character/1,2,3."""
        if not ids:
            return []
        model = RESOURCES[resource]
        unique = sorted(set(ids))
        try:
            data = await self._get_json(f"/{resource}/{','.join(map(str, unique))}")
        except NotFoundError:  # un seul id inexistant -> 404 au lieu d'une liste vide
            return []
        if isinstance(data, dict):  # un seul id -> l'API renvoie un objet, pas une liste
            data = [data]
        return [model(**d) for d in data]
