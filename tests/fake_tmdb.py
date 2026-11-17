"""Faux TMDB pour tester hors ligne.

Hypothèses NON VÉRIFIÉES (aucun appel réseau n'a servi à écrire ce fichier ;
à vérifier une fois à la main avec une vraie clé, puis corriger le fake) :
- H1. GET /tv/{show} renvoie `seasons: [{season_number, episode_count}]`, saison 0 comprise.
- H2. GET /tv/{show}/season/{n} renvoie `episodes: [{season_number, episode_number, name,
  air_date, overview, still_path, guest_stars: [{name, character}]}]`.
- H3. Le nom du personnage est dans `guest_stars[].character` (`name` = l'acteur).
- H4. `air_date` : « AAAA-MM-JJ », null ou "" ; `overview` souvent "" ; `still_path` peut être null.
- H5. Les mentions de crédit restent en anglais : « (voice) », « (uncredited) ».
- H6. Clé invalide : 401 ; limite de débit : 429. Le corps ne contient jamais la clé.

A17. La liste des saisons vaut 0, 1, 6, 7 (sans 2 à 5) : le faux R&M n'a pas ces saisons,
TMDB les rendrait complémentaires et gonflerait le catalogue sans rien tester de plus.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app.tmdb import TmdbClient

KEY = "SECRET-TMDB-KEY-42"  # valeur distinctive, recherchée dans les logs et les caches
DATA = json.loads((Path(__file__).parent / "fixtures" / "tmdb_sample.json").read_text())
calls: list[str] = []  # journal : request.url.path seulement (jamais la query, donc jamais la clé)


def transport(*, key: str = KEY, fail: dict | None = None, delay: float = 0) -> httpx.MockTransport:
    """`fail` (mutable, relu à chaque requête) : clé "show" ou numéro de saison (int) ;
    valeur 401, 429 ou "down" (ConnectError). `delay` > 0 force l'entrelacement des requêtes."""
    failures = fail if fail is not None else {}

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        m = re.fullmatch(r"/3/tv/(\d+)(?:/season/(\d+))?", request.url.path)
        if not m:
            return httpx.Response(404, json={"status_code": 34})
        season = int(m[2]) if m[2] else "show"
        mode = failures.get(season)
        if mode == "down":
            raise httpx.ConnectError("offline")
        if mode == 429:
            return httpx.Response(429, headers={"Retry-After": "0"},
                                  json={"status_code": 25, "status_message": "Rate limit"})
        if mode == 401 or request.url.params.get("api_key") != key:
            return httpx.Response(401, json={"status_code": 7, "status_message": "Invalid API key"})
        if season == "show":
            return httpx.Response(200, json=DATA["show"])
        body = DATA["seasons"].get(str(season))
        if body is None:
            return httpx.Response(404, json={"status_code": 34})
        return httpx.Response(200, json=body)

    if delay > 0:
        async def slow(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(delay)
            return respond(request)
        return httpx.MockTransport(slow)
    return httpx.MockTransport(respond)


def client(*, disk_ttl: int | None = None, **kw) -> TmdbClient:
    extra = {} if disk_ttl is None else {"disk_ttl": disk_ttl}
    return TmdbClient(KEY, transport=transport(**kw), **extra)
