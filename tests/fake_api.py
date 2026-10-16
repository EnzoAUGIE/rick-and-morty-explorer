"""Fausse API Rick & Morty pour tester hors ligne.

Les données (40 personnages, 21 lieux, 10 épisodes) viennent du dump MongoDB
de test du serveur officiel (github.com/EnzoAUGIE/rick-and-morty-api,
test/data/*.bson), converties au format JSON renvoyé par l'API.

Le comportement reproduit celui du serveur Node (routes/middlewares.js,
handlers/operations.js, models/*.js) :
- 20 résultats par page, `page > pages` -> 404 {"error": "There is nothing here"} ;
- filtres = regex insensible à la casse (gender "male" ancré au début) ;
- seuls les filtres autorisés par ressource sont pris en compte ;
- /character/1,2,3 et /character/[1,2,3] -> tableau ; /character/1 -> objet ;
- id inconnu -> 404 {"error": "Character not found"}.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

DATA = json.loads((Path(__file__).parent / "fixtures" / "api_sample.json").read_text())
LIMIT = 20
QUERIES = {
    "character": ["name", "status", "species", "type", "gender"],
    "location": ["name", "dimension", "type"],
    "episode": ["name", "episode"],
}
NOT_FOUND = {"character": "Character not found", "location": "Location not found",
             "episode": "Episode not found"}
BASE = "https://rickandmortyapi.com/api"

FAKE_JPEG = b"\xff\xd8\xff\xe0fake-jpeg"
calls: list[str] = []  # journal des requêtes (pour vérifier le cache)


def _json(data, status=200):
    return httpx.Response(status, json=data)


def _matches(value: str, key: str, pattern: str) -> bool:
    if key == "gender" and re.match(r"^male", pattern, re.I):
        return re.match(pattern, value, re.I) is not None
    return re.search(re.escape(pattern), value, re.I) is not None


def _by_id(resource: str, raw: str) -> httpx.Response:
    table = {item["id"]: item for item in DATA[resource]}
    if raw.startswith("[") and raw.endswith("]"):
        try:
            ids = json.loads(raw)
        except ValueError:
            return _json({"error": "Bad... bad array :/"}, 500)
        return _json([table[i] for i in sorted(set(ids)) if i in table])
    if "," in raw:
        ids = [int(x) for x in raw.split(",") if x.strip().isdigit()]
        return _json([table[i] for i in sorted(set(ids)) if i in table])
    if not raw.isdigit():
        return _json({"error": "Hey! you must provide an id"}, 500)
    item = table.get(int(raw))
    return _json(item) if item else _json({"error": NOT_FOUND[resource]}, 404)


def handler(request: httpx.Request) -> httpx.Response:
    calls.append(str(request.url))
    avatar = re.fullmatch(r"/api/character/avatar/(\d+)\.jpeg", request.url.path)
    if avatar:  # sur le vrai serveur : express.static sur le dossier images/
        known = any(c["id"] == int(avatar[1]) for c in DATA["character"])
        return httpx.Response(200, content=FAKE_JPEG) if known else _json(
            {"error": "There is nothing here"}, 404)
    m = re.fullmatch(r"/api/(character|location|episode)(?:/(.+))?", request.url.path)
    if not m:
        return _json({"error": "There is nothing here"}, 404)
    resource, raw_id = m[1], m[2]
    if raw_id:
        return _by_id(resource, raw_id)

    params = request.url.params
    filters = {k: params[k].strip() for k in QUERIES[resource] if params.get(k, "").strip()}
    items = [x for x in DATA[resource]
             if all(_matches(str(x[k]), k, v) for k, v in filters.items())]

    try:
        page = max(int(params.get("page", 1)), 1)
    except ValueError:
        page = 1
    pages = -(-len(items) // LIMIT)
    if page > pages:  # inclut le cas "aucun résultat"
        return _json({"error": "There is nothing here"}, 404)

    qs = "".join(f"&{k}={v}" for k, v in filters.items())
    url = f"{BASE}/{resource}?page="
    return _json({
        "info": {"count": len(items), "pages": pages,
                 "next": None if page >= pages else f"{url}{page + 1}{qs}",
                 "prev": None if page < 2 else f"{url}{page - 1}{qs}"},
        "results": items[(page - 1) * LIMIT: page * LIMIT],
    })


transport = httpx.MockTransport(handler)
