"""Tests de l'app avec la fausse API (données réelles du dump de test officiel)."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Character, id_from_url

from . import fake_api


# ---------- modèles
def test_id_from_url():
    assert id_from_url("https://rickandmortyapi.com/api/location/3") == 3
    assert id_from_url("") is None
    assert id_from_url(None) is None


def test_null_origin_becomes_unknown():
    raw = dict(fake_api.DATA["character"][0], origin=None)
    assert Character(**raw).origin.name == "unknown"


# ---------- fidélité de la fausse API au serveur officiel
def test_fake_api_matches_server_behaviour():
    with httpx.Client(transport=fake_api.transport, base_url=fake_api.BASE) as h:
        assert h.get("/character").json()["info"]["pages"] == 2         # 40 persos / 20
        assert h.get("/character?page=3").status_code == 404             # page > pages
        assert len(h.get("/character/[1,2]").json()) == 2                # syntaxe crochets
        assert len(h.get("/character/1,2").json()) == 2                  # syntaxe virgules
        assert isinstance(h.get("/character/1").json(), dict)            # id seul -> objet
        assert h.get("/character/999").json() == {"error": "Character not found"}
        males = h.get("/character?gender=male").json()["results"]
        assert all(c["gender"] == "Male" for c in males)                 # pas "Female"


# ---------- pages
def test_home_has_three_category_buttons(client):
    html = client.get("/").text
    for href in ('href="/characters"', 'href="/locations"', 'href="/episodes"'):
        assert href in html
    assert "theme-home" in html


@pytest.mark.parametrize("path,theme", [
    ("/characters", "theme-characters"),
    ("/locations", "theme-locations"),
    ("/episodes", "theme-episodes"),
])
def test_each_category_has_its_own_theme(client, path, theme):
    r = client.get(path)
    assert r.status_code == 200 and theme in r.text


def test_pagination(client):
    html = client.get("/characters").text
    assert "Page 1 / 2" in html and "page=2" in html
    html = client.get("/characters?page=2").text
    assert "Page 2 / 2" in html and "page=1" in html


def test_pagination_keeps_filters(client):
    html = client.get("/characters?name=rick").text
    assert "Rick Sanchez" in html and "Morty Smith" not in html
    html = client.get("/characters?status=dead").text
    assert "Adjudicator Rick" in html and "Rick Sanchez" not in html


def test_page_out_of_range_is_empty_not_error(client):
    r = client.get("/characters?page=99")
    assert r.status_code == 200 and "Aucun résultat" in r.text


def test_search_empty_result(client):
    r = client.get("/characters?name=zzz")
    assert r.status_code == 200 and "Aucun résultat" in r.text


def test_season_filter(client):
    html = client.get("/episodes?season=1").text
    assert "Pilot" in html and "S01E10" in html


# ---------- navigation croisée
def test_episode_links_to_characters_and_locations(client):
    html = client.get("/episodes/1").text
    assert "Pilot" in html
    for cid in (1, 2, 35, 38):
        assert f'href="/characters/{cid}"' in html
    assert 'href="/locations/20"' in html  # lieu actuel de Rick


def test_character_links_to_episodes_and_locations(client):
    html = client.get("/characters/1").text
    assert "Rick Sanchez" in html
    assert 'href="/episodes/1"' in html and 'href="/episodes/10"' in html
    assert 'href="/locations/1"' in html   # origine : Earth (C-137)
    assert 'href="/locations/20"' in html  # dernier lieu connu


def test_unknown_origin_is_not_a_link(client):
    html = client.get("/characters/2").text
    assert "chip-muted" in html and "unknown" in html


def test_location_links_to_residents(client):
    html = client.get("/locations/3").text
    assert "Citadel of Ricks" in html and 'href="/characters/8"' in html


def test_single_resident_batch_returns_list(client):
    # Abadango n'a qu'un résident : /character/6 renvoie un objet, à normaliser
    assert 'href="/characters/6"' in client.get("/locations/2").text


def test_next_episode_hidden_on_last(client):
    assert "Épisode suivant" in client.get("/episodes/9").text
    assert "Épisode suivant" not in client.get("/episodes/10").text


# ---------- robustesse
def test_404(client):
    r = client.get("/characters/999")
    assert r.status_code == 404 and "Introuvable" in r.text


def test_api_down_gives_503():
    def boom(request):
        raise httpx.ConnectError("offline")
    app = create_app(transport=httpx.MockTransport(boom), client_options={"backoff": 0})
    with TestClient(app) as c:
        r = c.get("/characters")
    assert r.status_code == 503 and "ConnectError" in r.text


def test_cache_avoids_duplicate_calls(client):
    client.get("/characters/1")
    n = len(fake_api.calls)
    client.get("/characters/1")
    assert len(fake_api.calls) == n
