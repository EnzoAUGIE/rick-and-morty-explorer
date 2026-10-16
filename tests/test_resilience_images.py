"""Fiabilité de l'accès API (nouvelles tentatives, cache) et images."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.client import RickMortyClient
from app.illustrations import kind_of, location_art
from app.main import create_app
from app.models import Location
from app.tmdb import TmdbClient

from . import fake_api


def flaky(fail_times: int, status: int = 429):
    """API qui échoue `fail_times` fois avant de répondre normalement."""
    state = {"n": 0}

    def handler(request):
        state["n"] += 1
        if state["n"] <= fail_times:
            return httpx.Response(status, headers={"retry-after": "0"})
        return fake_api.handler(request)
    return httpx.MockTransport(handler), state


# ---------- nouvelles tentatives
@pytest.mark.parametrize("status", [429, 502, 503])
def test_retry_then_success(status):
    transport, state = flaky(2, status)
    with TestClient(create_app(transport=transport, client_options={"backoff": 0})) as c:
        r = c.get("/characters?page=2")
    assert r.status_code == 200 and state["n"] == 3  # 2 échecs + 1 succès


def test_give_up_after_retries_shows_real_status():
    transport, state = flaky(99, 429)
    with TestClient(create_app(transport=transport,
                               client_options={"backoff": 0, "retries": 3})) as c:
        r = c.get("/characters")
    assert r.status_code == 503 and "HTTP 429" in r.text and state["n"] == 4


def test_stale_cache_used_when_api_down():
    import asyncio

    state = {"down": False}

    def handler(request):
        if state["down"]:
            raise httpx.ConnectError("offline")
        return fake_api.handler(request)

    async def scenario():
        cl = RickMortyClient(transport=httpx.MockTransport(handler), ttl=0, backoff=0)
        first = await cl.get("character", 1)
        state["down"] = True
        again = await cl.get("character", 1)  # cache expiré (ttl=0) mais API en panne
        await cl.aclose()
        return first, again

    first, again = asyncio.run(scenario())
    assert first.name == again.name == "Rick Sanchez"


# ---------- avatars
def test_avatar_downloaded_once_then_served_from_disk(client, tmp_cache):
    r = client.get("/media/character/1.jpeg")
    assert r.status_code == 200 and r.content == fake_api.FAKE_JPEG
    assert (tmp_cache / "avatars" / "1.jpeg").exists()
    n = len(fake_api.calls)
    client.get("/media/character/1.jpeg")
    assert len(fake_api.calls) == n  # aucune nouvelle requête vers l'API


def test_missing_avatar_returns_placeholder_not_cached(client, tmp_cache):
    r = client.get("/media/character/9999.jpeg")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg")
    assert not (tmp_cache / "avatars" / "9999.jpeg").exists()


def test_pages_use_local_avatars(client):
    html = client.get("/characters").text
    assert 'src="/media/character/1.jpeg"' in html
    assert "rickandmortyapi.com/api/character/avatar" not in html


# ---------- lieux
@pytest.mark.parametrize("t,kind", [
    ("Planet", "planet"), ("Space station", "station"), ("Dimension", "dimension"),
    ("Microverse", "verse"), ("Cluster", "cluster"), ("Resort", "place"), ("", "place"),
])
def test_location_kind(t, kind):
    assert kind_of(t) == kind


def test_location_art_is_deterministic_and_unique():
    a = Location(**fake_api.DATA["location"][0])
    b = Location(**fake_api.DATA["location"][1])
    assert location_art(a) == location_art(a)
    assert location_art(a) != location_art(b)
    assert str(location_art(a)).startswith("<svg")


def test_location_pages_have_art(client):
    assert client.get("/locations").text.count("<svg class=\"art\"") >= 10
    assert "<svg" in client.get("/locations/1").text


# ---------- épisodes
def test_episode_mosaic_without_tmdb(client):
    html = client.get("/episodes").text
    assert 'class="mosaic"' in html and "TMDB" not in html


def fake_tmdb():
    def handler(request):
        assert request.url.params["api_key"] == "k"
        season = int(request.url.path.rsplit("/", 1)[1])
        return httpx.Response(200, json={"episodes": [
            {"episode_number": n, "still_path": f"/s{season}e{n}.jpg"} for n in range(1, 12)]})
    return TmdbClient("k", transport=httpx.MockTransport(handler))


def test_episode_stills_with_tmdb():
    app = create_app(transport=fake_api.transport, client_options={"backoff": 0},
                     tmdb=fake_tmdb())
    with TestClient(app) as c:
        html = c.get("/episodes").text
        detail = c.get("/episodes/3").text
    assert "https://image.tmdb.org/t/p/w500/s1e1.jpg" in html
    assert "/s1e3.jpg" in detail and "TMDB" in detail


def test_tmdb_failure_falls_back_to_mosaic():
    broken = TmdbClient("k", transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    app = create_app(transport=fake_api.transport, client_options={"backoff": 0}, tmdb=broken)
    with TestClient(app) as c:
        r = c.get("/episodes")
    assert r.status_code == 200 and 'class="mosaic"' in r.text


def test_mosaic_prefers_guest_characters():
    from app.models import Episode
    ep = Episode(**fake_api.DATA["episode"][0])  # Pilot : 1, 2, 35, 38, 62…
    assert ep.cover_avatars[0] == "/media/character/35.jpeg"
    assert len(ep.cover_avatars) == 4
