"""Cas limites du catalogue (QA) : données TMDB mal formées, ids, pagination, caches, concurrence.

Même seam que test_catalogue.py : create_app + TestClient, transports simulés, hors ligne.
"""
import asyncio
import copy
import json
import re
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app
from app.tmdb import TmdbClient

from . import fake_api, fake_tmdb


def _start(tmdb, **client_options):
    return TestClient(create_app(transport=fake_api.transport,
                                 client_options={"backoff": 0, **client_options}, tmdb=tmdb))


def _tmdb_serving(show, seasons):
    """Faux TMDB minimal : `show` et `seasons` sont renvoyés tels quels (même mal formés)."""
    def respond(request: httpx.Request) -> httpx.Response:
        m = re.fullmatch(r"/3/tv/\d+(?:/season/(\d+))?", request.url.path)
        body = seasons.get(int(m[1])) if m and m[1] else show
        if body is None:
            return httpx.Response(404, json={"status_code": 34})
        if isinstance(body, str):
            return httpx.Response(200, text=body)
        return httpx.Response(200, json=body)
    return TmdbClient(fake_tmdb.KEY, transport=httpx.MockTransport(respond))


def _show(*numbers):
    return {"seasons": [{"season_number": n} for n in numbers]}


# ---------- entrées HTTP invalides
@pytest.mark.parametrize("path", ["/episodes/0", "/episodes/-1", "/episodes/600",
                                  "/episodes/99999999999999999999999", "/episodes/10001"])
@pytest.mark.parametrize("fixture", ["client", "full_client"])
def test_invalid_episode_ids_give_404(request, fixture, path):
    c = request.getfixturevalue(fixture)
    r = c.get(path, follow_redirects=False)
    assert r.status_code == 404 and "Introuvable" in r.text


@pytest.mark.parametrize("path", ["/episodes/abc", "/episodes/1.5", "/episodes?page=0",
                                  "/episodes?page=-1", "/episodes?page=abc"])
def test_non_integer_ids_and_pages_are_rejected_with_422(full_client, path):
    assert full_client.get(path).status_code == 422


@pytest.mark.parametrize("query", ["season=abc", "season=-1", "season=3.5", "season=", "name=%00"])
def test_odd_filters_never_crash(full_client, query):
    assert full_client.get(f"/episodes?{query}").status_code == 200


def test_season_filter_with_non_ascii_digit_does_not_crash(full_client):
    """BUG (hérité de main, conservé par la réécriture) : `"²".isdigit()` vaut True mais
    `int("²")` lève ValueError -> 500 au lieu de 200 (filtre ignoré)."""
    r = full_client.get("/episodes", params={"season": "²"})
    assert r.status_code == 200


def test_page_beyond_the_end_is_empty_but_ok(full_client):
    r = full_client.get("/episodes?page=99")
    assert r.status_code == 200 and "Aucun résultat" in r.text and "Suivant" not in r.text


def test_deterministic_id_redirect_also_works_without_key(client):
    r = client.get("/episodes/101", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "/episodes/1"
    assert client.get("/episodes/601").status_code == 404  # sans TMDB, 601 n'existe pas


# ---------- données TMDB mal formées : la page ne casse jamais
def test_malformed_tmdb_entries_are_tolerated(caplog):
    junk_season = {"episodes": [
        "pas un dict", None, 7,
        {"episode_number": "3", "name": "Numéro texte"},          # numéro non entier : ignoré
        {"episode_number": 1, "name": None, "air_date": 20220904, "overview": None,
         "still_path": 5, "guest_stars": None},                    # tout est du mauvais type
        {"episode_number": 2, "name": "Date vide", "air_date": ""},
        {"episode_number": 3, "name": "Date folle", "air_date": "2022-13-45",
         "guest_stars": {"character": "Rick"}},
        {"episode_number": 4, "name": "Invités bizarres",
         "guest_stars": ["x", None, {"character": None}, {"character": 3}, {"name": "sans rôle"}]},
        {"episode_number": 4, "name": "Doublon du code S06E04"},
        {"episode_number": 99, "name": "Dernier encodable"},
        {"episode_number": 100, "name": "Trop grand pour l'id"},
        {"episode_number": 0, "name": "Numéro zéro"},
    ]}
    tmdb = _tmdb_serving(_show(6), {6: junk_season})
    with caplog.at_level("WARNING"):
        with _start(tmdb) as c:
            r = c.get("/episodes?season=6")
            assert r.status_code == 200
            ids = re.findall(r'class="card" href="/episodes/(\d+)"', r.text)
            assert ids == ["601", "602", "603", "604", "699"]
            for ep_id in ids:
                assert c.get(f"/episodes/{ep_id}").status_code == 200
            assert "Date inconnue" in c.get("/episodes/603").text
            assert "Aucun invité connu." in c.get("/episodes/604").text
            assert c.get("/episodes/700").status_code == 404  # S07E00 n'existe pas
    assert fake_tmdb.KEY not in caplog.text


@pytest.mark.parametrize("show,seasons", [
    ({"seasons": "oups"}, {}),
    ({"seasons": [None, {"season_number": "6"}, {"season_number": 0}]}, {}),
    ({}, {}),
    ("<html>pas du json</html>", {}),
    ([1, 2, 3], {}),
    (_show(6), {6: "<html>pas du json</html>"}),
    (_show(6), {6: {"episodes": "oups"}}),
    (_show(6), {6: [1, 2]}),
    (_show(6), {}),  # saison annoncée mais 404
])
def test_unusable_tmdb_payloads_fall_back_to_rm_only(show, seasons):
    with _start(_tmdb_serving(show, seasons)) as c:
        r = c.get("/episodes")
    assert r.status_code == 200 and "<small>10</small>" in r.text and "TMDB" not in r.text


def test_season_announced_but_missing_keeps_other_seasons():
    show = copy.deepcopy(fake_tmdb.DATA["show"])
    show["seasons"].append({"season_number": 8})  # TMDB répond 404 pour la saison 8
    tmdb = _tmdb_serving(show, {int(k): v for k, v in fake_tmdb.DATA["seasons"].items()})
    with _start(tmdb) as c:
        r = c.get("/episodes")
    assert r.status_code == 200 and "<small>23</small>" in r.text


def test_tmdb_text_is_html_escaped():
    season = {"episodes": [{"episode_number": 1, "name": "<script>alert(1)</script>",
                            "overview": "<b>gras</b>",
                            "guest_stars": [{"character": "<img src=x onerror=y>"}]}]}
    with _start(_tmdb_serving(_show(6), {6: season})) as c:
        pages = [c.get("/episodes?season=6").text, c.get("/episodes/601").text]
    for html in pages:
        assert "<script>alert(1)</script>" not in html and "<img src=x" not in html
    assert "&lt;b&gt;gras&lt;/b&gt;" in pages[1]


def test_catalogue_is_sorted_even_if_tmdb_is_not():
    seasons = {int(k): copy.deepcopy(v) for k, v in fake_tmdb.DATA["seasons"].items()}
    seasons[6]["episodes"].reverse()
    show = _show(7, 6, 1)  # saisons dans le désordre aussi
    with _start(_tmdb_serving(show, seasons)) as c:
        html = c.get("/episodes?season=6").text
        ids = re.findall(r'class="card" href="/episodes/(\d+)"', html)
        assert ids == [str(i) for i in range(601, 611)]
        assert c.get("/episodes?page=2").text.index("S07E01") < c.get("/episodes?page=2").text.index("S07E03")
        assert "Position : 11 / 23" in c.get("/episodes/601").text


# ---------- pagination aux frontières de 20
def _with_season6_size(monkeypatch, size):
    data = copy.deepcopy(fake_tmdb.DATA)
    data["show"]["seasons"] = [s for s in data["show"]["seasons"] if s["season_number"] != 7]
    base = data["seasons"]["6"]["episodes"][0]
    data["seasons"]["6"]["episodes"] = [
        dict(base, episode_number=n, name=f"Épisode {n}", guest_stars=[]) for n in range(1, size + 1)]
    monkeypatch.setattr(fake_tmdb, "DATA", data)


def test_exactly_one_full_page_has_no_second_page(monkeypatch):
    _with_season6_size(monkeypatch, 10)  # 10 R&M + 10 = 20
    with _start(fake_tmdb.client()) as c:
        html = c.get("/episodes").text
        assert "<small>20</small>" in html and "Page 1 /" not in html and "Suivant" not in html
        assert "Aucun résultat" in c.get("/episodes?page=2").text


def test_twenty_first_episode_goes_alone_to_page_two(monkeypatch):
    _with_season6_size(monkeypatch, 11)
    with _start(fake_tmdb.client()) as c:
        assert "Page 1 / 2" in c.get("/episodes").text
        page2 = c.get("/episodes?page=2").text
    assert page2.count('class="card"') == 1 and 'href="/episodes/611"' in page2


# ---------- invités : cas limites de normalisation
def test_guest_normalisation_edge_cases():
    season = {"episodes": [{"episode_number": 1, "name": "Invités", "guest_stars": [
        {"character": "Rick Sanchez (VOICE)"}, {"character": " / "}, {"character": "(uncredited)"},
        {"character": "rick   sanchez"}, {"character": "Évelyne Inconnue / Morty Smith (Voice)"},
    ]}]}
    with _start(_tmdb_serving(_show(6), {6: season})) as c:
        html = c.get("/episodes/601").text
    assert html.count('href="/characters/1"') == 1 and ">Rick Sanchez</a>" in html
    assert html.count('href="/characters/2"') == 1 and ">Morty Smith</a>" in html
    assert '<span class="chip chip-muted">Évelyne Inconnue</span>' in html
    assert 'chip-muted"></span>' not in html and "(Voice)" not in html and "(VOICE)" not in html
    assert not any("%C3%89" in call or "É" in call for call in fake_api.calls)  # recherche sans accent


# ---------- cache disque TMDB : contenus valides mais inattendus
@pytest.mark.parametrize("content", [
    lambda: {"at": time.time(), "data": [1, 2]},             # frais, mauvais type
    lambda: {"at": time.time(), "data": "texte"},
    lambda: {"at": time.time() + 10_000, "data": {}},        # horloge reculée : périmé
    lambda: {"at": "hier", "data": {}},
    lambda: {"data": {}},
    lambda: [],
    lambda: None,
])
def test_tmdb_cache_with_unexpected_content_is_ignored(tmp_cache, content):
    with _start(fake_tmdb.client()) as c:
        c.get("/episodes")
    for f in (tmp_cache / "tmdb").iterdir():
        f.write_text(json.dumps(content()))
    fake_tmdb.calls.clear()
    with _start(fake_tmdb.client()) as c:
        r = c.get("/episodes")
    assert r.status_code == 200 and 'href="/episodes/601"' in r.text and fake_tmdb.calls


def test_stale_cache_with_unexpected_type_is_not_served_when_tmdb_is_down(tmp_cache):
    with _start(fake_tmdb.client()) as c:
        c.get("/episodes")
    for f in (tmp_cache / "tmdb").iterdir():
        f.write_text(json.dumps({"at": 0, "data": [1, 2]}))
    with _start(fake_tmdb.client(fail={"show": "down"})) as c:
        r = c.get("/episodes")
    assert r.status_code == 200 and "<small>10</small>" in r.text


def test_api_key_never_in_logs_on_success_path(caplog):
    with caplog.at_level("DEBUG"):
        with _start(fake_tmdb.client()) as c:
            for path in ("/episodes", "/episodes/601", "/episodes/103", "/episodes/9999"):
                c.get(path)
    assert fake_tmdb.KEY not in caplog.text
    assert all(fake_tmdb.KEY not in rec.getMessage() for rec in caplog.records)


# ---------- bugs trouvés : tests volontairement rouges
def test_concurrent_first_visits_to_a_detail_search_each_guest_once():
    """BUG : la résolution des invités n'est pas protégée contre la concurrence. Cinq premières
    visites simultanées de /episodes/601 refont chacune les 8 recherches (40 appels au lieu de 8),
    contrairement à « chaque nom distinct coûte au plus une requête » (spec, PLAN A1)."""
    async def slow_api(request):  # latence : force l'entrelacement des requêtes concurrentes
        await asyncio.sleep(0.01)
        return fake_api.handler(request)

    app = create_app(transport=httpx.MockTransport(slow_api), client_options={"backoff": 0},
                     tmdb=fake_tmdb.client())

    async def scenario():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url="http://test") as http:
                await http.get("/episodes")  # construit le catalogue
                fake_api.calls.clear()
                return await asyncio.gather(*(http.get("/episodes/601") for _ in range(5)))

    responses = asyncio.run(scenario())
    searches = [c for c in fake_api.calls if "/api/character?" in c]
    assert all(r.status_code == 200 for r in responses)
    assert len(searches) == len(set(searches))


def test_failed_partial_rebuild_keeps_the_previous_catalogue(monkeypatch):
    """BUG : PLAN A8 « si une reconstruction échoue, on garde l'ancien état ». Ici R&M répond
    mais la page 2 est en 429 sans aucun cache : la reconstruction partielle remplace un catalogue
    complet (23 épisodes) par 5 épisodes R&M, et les épisodes complémentaires disparaissent."""
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 0)  # reconstruction à chaque requête

    def handler(request):
        if request.url.path == "/api/episode" and request.url.params.get("page") == "2":
            return httpx.Response(429, headers={"retry-after": "0"})
        return fake_api.handler(request)

    app = create_app(transport=httpx.MockTransport(handler),
                     client_options={"backoff": 0, "retries": 1, "ttl": 0, "disk_ttl": 0},
                     tmdb=fake_tmdb.client())
    with TestClient(app) as c:
        assert "<small>23</small>" in c.get("/episodes").text
        monkeypatch.setattr(fake_api, "LIMIT", 5)  # R&M pagine autrement : la page 2 est inconnue du cache
        r = c.get("/episodes")
    assert r.status_code == 200 and "<small>23</small>" in r.text
