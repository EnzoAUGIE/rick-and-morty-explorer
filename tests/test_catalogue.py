"""Catalogue des épisodes (R&M + épisodes complémentaires), testé au seam applicatif."""
import pytest
from fastapi.testclient import TestClient

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
