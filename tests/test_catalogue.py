"""Catalogue des épisodes (R&M + épisodes complémentaires), testé au seam applicatif."""
import asyncio
import copy
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app
from app.tmdb import TmdbClient

from . import fake_api, fake_tmdb


# ---------- catalogue R&M seul : liste
def test_list_counts_episodes_and_offers_only_present_seasons(client):
    html = client.get("/episodes").text
    assert "<small>10</small>" in html
    assert "Saison 1</option>" in html and "Saison 2</option>" not in html


def test_name_filter_is_case_insensitive_contains(client):
    html = client.get("/episodes?name=PILOT").text
    assert "Pilot" in html and "Lawnmower Dog" not in html


def test_season_without_episode_gives_empty_page(client):
    r = client.get("/episodes?season=2")
    assert r.status_code == 200 and "Aucun résultat" in r.text


def test_catalogue_is_built_lazily(client):
    assert fake_api.calls == []  # le démarrage ne construit rien
    client.get("/characters")
    assert not any("/api/episode" in c for c in fake_api.calls)


def test_catalogue_is_built_once(client):
    client.get("/episodes")
    client.get("/episodes")
    assert sum("/api/episode?page=1" in c for c in fake_api.calls) == 1


# ---------- catalogue R&M seul : détail
def test_first_episode_has_no_previous(client):
    html = client.get("/episodes/1").text
    assert "Épisode précédent" not in html and "Épisode suivant" in html


def test_detail_shows_position_in_catalogue(client):
    assert "Position : 3 / 10" in client.get("/episodes/3").text


def test_unknown_episode_ids_give_404(client):
    for episode_id in (52, 999):
        r = client.get(f"/episodes/{episode_id}")
        assert r.status_code == 404 and "Introuvable" in r.text


# ---------- images TMDB portées par les épisodes R&M
def test_rm_episode_wins_and_gets_tmdb_image(full_client):
    html = full_client.get("/episodes").text
    assert "https://image.tmdb.org/t/p/w500/s1e1.jpg" in html
    assert "Pilot" in html and ">Pilote<" not in html


def test_season_zero_is_never_requested(full_client):
    full_client.get("/episodes")
    assert any(c.endswith("/season/1") for c in fake_tmdb.calls)
    assert not any("/season/0" in c for c in fake_tmdb.calls)


def test_without_key_serves_rm_with_warning_and_no_tmdb_call(caplog):
    app = create_app(transport=fake_api.transport, client_options={"backoff": 0},
                     tmdb=TmdbClient(""))
    fake_tmdb.calls.clear()
    with caplog.at_level("WARNING", logger="app"):
        with TestClient(app) as c:
            html = c.get("/episodes").text
    assert "<small>10</small>" in html and "TMDB" not in html
    assert fake_tmdb.calls == []
    assert "TMDB_API_KEY" in caplog.text


@pytest.mark.parametrize("failure", ["down", 401])
def test_tmdb_down_serves_rm_with_mosaic(failure, caplog):
    app = create_app(transport=fake_api.transport, client_options={"backoff": 0},
                     tmdb=fake_tmdb.client(fail={"show": failure}))
    with caplog.at_level("WARNING", logger="app.tmdb"):
        with TestClient(app) as c:
            r = c.get("/episodes")
    assert r.status_code == 200 and "<small>10</small>" in r.text
    assert 'class="mosaic"' in r.text and "TMDB" not in r.text
    assert [rec for rec in caplog.records if rec.levelname == "WARNING"]
    assert fake_tmdb.KEY not in caplog.text


# ---------- épisodes complémentaires : fusion, liste, détail, données partielles
def _card(html: str, episode_id: int) -> str:
    m = re.search(rf'<a class="card" href="/episodes/{episode_id}">(.*?)</a>', html, re.S)
    assert m, f"carte {episode_id} absente"
    return m[1]


def test_catalogue_adds_complementary_episodes(full_client):
    html = full_client.get("/episodes").text
    assert "<small>23</small>" in html and "Page 1 / 2" in html
    assert re.findall(r'<option value="(\d+)"', html) == ["1", "6", "7"]
    page2 = full_client.get("/episodes?page=2").text
    assert "Page 2 / 2" in page2 and "page=1" in page2
    assert all(code in page2 for code in ("S07E01", "S07E02", "S07E03"))


def test_rm_wins_and_season_zero_is_excluded(full_client):
    html = full_client.get("/episodes").text
    assert not any(f'href="/episodes/{i}"' in html for i in range(101, 111))
    assert "S00" not in html and "Saison 0" not in html


def test_season_filter_on_complementary_season(full_client):
    html = full_client.get("/episodes?season=6").text
    assert html.count('class="card" href="/episodes/6') == 10
    assert all(f'href="/episodes/{i}"' in html for i in range(601, 611))
    assert "Aucun résultat" in full_client.get("/episodes?season=8").text


def test_name_filter_across_sources(full_client):
    html = full_client.get("/episodes?name=solaricks").text
    assert 'href="/episodes/601"' in html and "<small>1</small>" in html
    assert "Aucun résultat" in full_client.get("/episodes?name=sol&season=7").text


def test_pagination_keeps_name_and_season(full_client, monkeypatch):
    monkeypatch.setattr("app.catalogue.PAGE_SIZE", 4)
    html = full_client.get("/episodes?name=i&season=6").text
    link = re.search(r'href="([^"]+)">Suivant', html)[1]
    assert "Page 1 / 3" in html and "page=2" in link and "name=i" in link and "season=6" in link


def test_complementary_card_has_no_character_count(full_client):
    html = full_client.get("/episodes?season=6").text
    card = _card(html, 601)
    assert "personnages" not in card and "September 4, 2022" in card
    assert "source TMDB" in card
    assert "19 personnages" in _card(full_client.get("/episodes").text, 1)


def test_complementary_detail_full(full_client):
    html = full_client.get("/episodes/601").text
    assert full_client.get("/episodes/601").status_code == 200
    assert "Solaricks" in html and "September 4, 2022" in html
    assert "Rick et Morty explorent un monde solaire." in html
    assert "https://image.tmdb.org/t/p/w500/s6e1.jpg" in html and "source TMDB" in html
    assert "Position : 11 / 23" in html
    assert 'href="/episodes/10"' in html and 'href="/episodes/602"' in html
    assert 'class="season-ep current"' in html
    assert "personnages" not in html and "themoviedb.org" in html


def test_complementary_detail_with_partial_data(full_client):
    html = full_client.get("/episodes/602").text
    assert "Date inconnue" in html and "Résumé indisponible" in html
    assert "cover-empty" in html and "Aucun invité connu." in html


def test_next_link_crosses_from_rm_to_complementary(full_client):
    assert 'href="/episodes/601"' in full_client.get("/episodes/10").text


# ---------- ids déterministes et redirection 301 (ADR-0001)
def test_deterministic_id_of_rm_episode_redirects(full_client):
    r = full_client.get("/episodes/103", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "/episodes/3"


def test_episode_added_by_rm_later_replaces_complementary(full_client, monkeypatch):
    data = copy.deepcopy(fake_api.DATA)
    data["episode"].append(dict(
        data["episode"][0], id=11, name="Solaricks (R&M)", episode="S06E01",
        characters=[f"{fake_api.BASE}/character/1"], url=f"{fake_api.BASE}/episode/11"))
    monkeypatch.setattr(fake_api, "DATA", data)
    moved = full_client.get("/episodes/601", follow_redirects=False)
    assert moved.status_code == 301 and moved.headers["location"] == "/episodes/11"
    html = full_client.get("/episodes").text
    assert html.count("S06E01") == 1 and "<small>23</small>" in html
    assert "source TMDB" not in _card(html, 11)
    assert full_client.get("/episodes/11").status_code == 200


def test_undecodable_or_unknown_ids_give_404(full_client):
    for episode_id in (600, 199, 700, 1000):
        assert full_client.get(f"/episodes/{episode_id}", follow_redirects=False).status_code == 404


# ---------- invités : normalisation et correspondance avec les fiches
def _character_searches() -> list[str]:
    return [c for c in fake_api.calls if "/api/character?" in c]


def test_guests_are_linked_to_characters(full_client):
    html = full_client.get("/episodes/601").text
    for cid in (1, 4, 7, 3, 2, 11, 22):
        assert f'href="/characters/{cid}"' in html
    assert 'href="/characters/38"' not in html and 'href="/characters/39"' not in html
    assert html.count('href="/characters/1"') == 1  # doublon (voice) / (uncredited) supprimé


def test_unmatched_guest_stays_plain_text_and_mentions_are_removed(full_client):
    html = full_client.get("/episodes/601").text
    assert '<span class="chip chip-muted">Birdperson</span>' in html
    assert "(voice)" not in html and "(uncredited)" not in html
    assert ">Aqua (Rick)</a>" in html  # parenthèse hors liste fermée : conservée
    assert re.search(r'href="/characters/\d+">Summer Smith</a>', html)
    assert re.search(r'href="/characters/\d+">Morty Smith</a>', html)


def test_guest_resolution_is_lazy_and_memorised(full_client):
    full_client.get("/episodes")
    assert _character_searches() == []  # la liste ne résout aucun invité
    full_client.get("/episodes/601")
    first = len(_character_searches())
    assert 0 < first <= 8  # au plus une requête par nom distinct
    full_client.get("/episodes/601")
    assert len(_character_searches()) == first


def test_resolved_guests_survive_restart_with_only_unmatched_names_requested():
    def start():
        return TestClient(create_app(transport=fake_api.transport, client_options={"backoff": 0},
                                     tmdb=fake_tmdb.client()))
    with start() as c:
        assert 'href="/characters/11"' in c.get("/episodes/601").text
    fake_api.calls.clear()
    with start() as c:
        assert 'href="/characters/11"' in c.get("/episodes/601").text
    # les fiches trouvées viennent du cache disque ; une recherche vide est un 404, jamais
    # mis en cache (test_not_found_is_not_cached_on_disk) : seul « Birdperson » est redemandé
    assert [c for c in fake_api.calls if "Birdperson" not in c] == []


def test_rm_outage_during_guest_resolution_gives_plain_text_then_recovers():
    state = {"down": True}

    def handler(request):
        if state["down"] and request.url.path == "/api/character":
            return httpx.Response(503)
        return fake_api.handler(request)

    app = create_app(transport=httpx.MockTransport(handler),
                     client_options={"backoff": 0}, tmdb=fake_tmdb.client())
    with TestClient(app) as c:
        r = c.get("/episodes/601")
        assert r.status_code == 200 and '<span class="chip chip-muted">Rick Sanchez</span>' in r.text
        assert 'href="/characters/1"' not in r.text
        state["down"] = False  # la panne n'a pas été mémorisée
        assert 'href="/characters/1"' in c.get("/episodes/601").text


# ---------- cache disque TMDB et secret
def _start(tmdb):
    return TestClient(create_app(transport=fake_api.transport, client_options={"backoff": 0},
                                 tmdb=tmdb))


def test_tmdb_cache_reused_after_restart(tmp_cache):
    with _start(fake_tmdb.client()) as c:
        c.get("/episodes")
    fake_tmdb.calls.clear()
    with _start(fake_tmdb.client()) as c:
        assert 'href="/episodes/601"' in c.get("/episodes").text
    assert fake_tmdb.calls == []


def test_tmdb_cache_expires_after_ttl(tmp_cache):
    with _start(fake_tmdb.client(disk_ttl=0)) as c:
        c.get("/episodes")
    fake_tmdb.calls.clear()
    with _start(fake_tmdb.client(disk_ttl=0)) as c:
        c.get("/episodes")
    assert fake_tmdb.calls


def test_stale_tmdb_cache_used_when_tmdb_down(tmp_cache, caplog):
    with _start(fake_tmdb.client(disk_ttl=0)) as c:
        c.get("/episodes")
    down = {"show": "down", 1: "down", 6: "down", 7: "down"}
    with caplog.at_level("WARNING", logger="app.tmdb"):
        with _start(fake_tmdb.client(disk_ttl=0, fail=down)) as c:
            assert 'href="/episodes/601"' in c.get("/episodes").text
    assert "périmé" in caplog.text and fake_tmdb.KEY not in caplog.text


def test_unreadable_tmdb_cache_is_ignored(tmp_cache):
    with _start(fake_tmdb.client()) as c:
        c.get("/episodes")
    for f in (tmp_cache / "tmdb").iterdir():
        f.write_text("{pas du json")
    fake_tmdb.calls.clear()
    with _start(fake_tmdb.client()) as c:
        r = c.get("/episodes")
    assert r.status_code == 200 and 'href="/episodes/601"' in r.text and fake_tmdb.calls


def test_tmdb_cache_write_failure_leaves_no_file(tmp_cache, monkeypatch):
    with _start(fake_tmdb.client()) as c:
        c.get("/episodes")
    files = list((tmp_cache / "tmdb").iterdir())
    assert files and all(f.suffix == ".json" for f in files)  # pas de fichier temporaire

    def boom(*a, **k):
        raise OSError("disque plein")
    monkeypatch.setattr("app.disk_cache.os.replace", boom)
    for f in files:
        f.unlink()
    with _start(fake_tmdb.client()) as c:
        r = c.get("/episodes")
    assert r.status_code == 200 and 'href="/episodes/601"' in r.text
    assert not list((tmp_cache / "tmdb").glob("*"))


def test_tmdb_failure_is_not_cached(tmp_cache):
    with _start(fake_tmdb.client(fail={6: 429})) as c:
        assert 'href="/episodes/601"' not in c.get("/episodes").text
    fake_tmdb.calls.clear()
    with _start(fake_tmdb.client()) as c:
        assert 'href="/episodes/601"' in c.get("/episodes").text
    assert [p.rsplit("/", 1)[1] for p in fake_tmdb.calls] == ["6"]


def test_tmdb_cache_key_does_not_depend_on_api_key(tmp_cache):
    with _start(fake_tmdb.client()) as c:
        c.get("/episodes")
    fake_tmdb.calls.clear()
    other = TmdbClient("AUTRE-CLE", transport=fake_tmdb.transport(key="AUTRE-CLE"))
    with _start(other) as c:
        assert 'href="/episodes/601"' in c.get("/episodes").text
    assert fake_tmdb.calls == []


@pytest.mark.parametrize("failure", [401, 429, "down"])
def test_api_key_never_in_logs_on_tmdb_failure(failure, caplog):
    with caplog.at_level("DEBUG"):
        with _start(fake_tmdb.client(fail={"show": failure, 1: failure, 6: failure})) as c:
            c.get("/episodes")
    assert fake_tmdb.KEY not in caplog.text
    assert all(fake_tmdb.KEY not in rec.getMessage() for rec in caplog.records)


# ---------- résilience de la construction à froid et concurrence
def _always_429(request):
    return httpx.Response(429, headers={"retry-after": "0"})


def test_cold_build_survives_429_and_outage(tmp_cache):
    with _start(fake_tmdb.client(disk_ttl=0)) as c:  # un premier app sain remplit les caches
        c.get("/episodes")
        c.get("/episodes/601")
    app = create_app(transport=httpx.MockTransport(_always_429),
                     client_options={"backoff": 0, "retries": 1, "disk_ttl": 0},
                     tmdb=fake_tmdb.client(disk_ttl=0, fail={"show": 429, 1: "down",
                                                              6: 429, 7: "down"}))
    with TestClient(app) as c:
        r = c.get("/episodes")
        assert r.status_code == 200 and "Pilot" in r.text and "<small>23</small>" in r.text
        assert c.get("/episodes/601").status_code == 200


def test_cold_build_tmdb_season_429_without_cache(caplog):
    with caplog.at_level("WARNING"):
        with _start(fake_tmdb.client(fail={6: 429})) as c:
            r = c.get("/episodes")
    assert r.status_code == 200 and "<small>13</small>" in r.text
    assert 'href="/episodes/601"' not in r.text
    assert "HTTP 429" in caplog.text and fake_tmdb.KEY not in caplog.text


def test_cold_build_partial_rm_pages_adds_no_complementary_episode(monkeypatch):
    monkeypatch.setattr(fake_api, "LIMIT", 5)

    def handler(request):
        if request.url.path == "/api/episode" and request.url.params.get("page") == "2":
            return httpx.Response(429, headers={"retry-after": "0"})
        return fake_api.handler(request)

    app = create_app(transport=httpx.MockTransport(handler),
                     client_options={"backoff": 0, "retries": 1}, tmdb=fake_tmdb.client())
    with TestClient(app) as c:
        r = c.get("/episodes")
    assert r.status_code == 200 and "<small>5</small>" in r.text
    assert "S01E01" in r.text and "S01E05" in r.text and "S01E06" not in r.text
    assert 'href="/episodes/6' not in r.text and "source TMDB" not in r.text
    assert "https://image.tmdb.org/t/p/w500/s1e1.jpg" in r.text


def test_cold_build_rm_down_without_cache_gives_503():
    def down(request):
        raise httpx.ConnectError("offline")
    app = create_app(transport=httpx.MockTransport(down), client_options={"backoff": 0},
                     tmdb=fake_tmdb.client())
    with TestClient(app) as c:
        r = c.get("/episodes")
    assert r.status_code == 503 and "ConnectError" in r.text


def test_incomplete_catalogue_is_rebuilt_later(monkeypatch):
    monkeypatch.setattr(config, "CATALOGUE_RETRY_SECONDS", 0)
    fail = {6: 429}
    with _start(fake_tmdb.client(fail=fail)) as c:
        assert 'href="/episodes/601"' not in c.get("/episodes").text
        fail.clear()
        fake_tmdb.calls.clear()
        assert 'href="/episodes/601"' in c.get("/episodes").text
    assert not any(p.endswith("/season/1") for p in fake_tmdb.calls)  # servi par le cache disque


def test_complete_catalogue_not_rebuilt_within_ttl(full_client):
    full_client.get("/episodes/3")
    fake_api.calls.clear()
    fake_tmdb.calls.clear()
    for _ in range(3):
        full_client.get("/episodes")
    full_client.get("/episodes/3")
    assert fake_api.calls == [] and fake_tmdb.calls == []


def test_complete_catalogue_is_rebuilt_after_ttl_and_keeps_old_state_on_failure(monkeypatch):
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 0)
    state = {"down": False}

    def handler(request):
        if state["down"]:
            raise httpx.ConnectError("offline")
        return fake_api.handler(request)

    app = create_app(transport=httpx.MockTransport(handler),
                     client_options={"backoff": 0, "ttl": 0, "disk_ttl": 0}, tmdb=fake_tmdb.client())
    with TestClient(app) as c:
        assert "<small>23</small>" in c.get("/episodes").text
        state["down"] = True  # la reconstruction échoue : l'ancien catalogue reste servi
        r = c.get("/episodes")
        assert r.status_code == 200 and "<small>23</small>" in r.text


def test_cold_cost_is_bounded(tmp_cache):
    with _start(fake_tmdb.client()) as c:
        c.get("/episodes")
    assert sum("/api/episode" in call for call in fake_api.calls) == 1
    assert [p.split("60625")[1] for p in fake_tmdb.calls] == ["", "/season/1", "/season/6", "/season/7"]
    fake_api.calls.clear()
    fake_tmdb.calls.clear()
    with _start(fake_tmdb.client()) as c:  # redémarrage : tout vient des caches disque
        c.get("/episodes")
    assert fake_api.calls == [] and fake_tmdb.calls == []


def test_concurrent_cold_requests_build_the_catalogue_once():
    app = create_app(transport=fake_api.transport, client_options={"backoff": 0},
                     tmdb=fake_tmdb.client(delay=0.01))

    async def scenario():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url="http://test") as http:
                return await asyncio.gather(*(http.get("/episodes") for _ in range(5)))

    fake_api.calls.clear()
    fake_tmdb.calls.clear()
    responses = asyncio.run(scenario())
    assert all(r.status_code == 200 and "<small>23</small>" in r.text for r in responses)
    assert len(fake_tmdb.calls) == len(set(fake_tmdb.calls)) == 4
    assert sum("/api/episode?page=1" in c for c in fake_api.calls) == 1


# ---------- attribution conditionnelle et pages inchangées
@pytest.mark.parametrize("path", ["/episodes/601", "/episodes?season=6", "/episodes?season=7"])
def test_attribution_shown_when_complementary_episodes_are_visible(full_client, path):
    # ?season=7 : épisodes complémentaires sans aucune image, l'attribution reste affichée
    html = full_client.get(path).text
    assert "themoviedb.org" in html and "Épisodes complémentaires et images" in html


@pytest.mark.parametrize("path", ["/episodes", "/episodes/1", "/characters/1", "/locations/3"])
def test_no_tmdb_mention_without_key(client, path):
    assert "TMDB" not in client.get(path).text


@pytest.mark.parametrize("path", ["/characters/1", "/locations/3"])
def test_character_and_location_pages_ignore_complementary_episodes(full_client, path):
    html = full_client.get(path).text
    assert not re.search(r'href="/episodes/[1-9]\d\d"', html) and "TMDB" not in html
