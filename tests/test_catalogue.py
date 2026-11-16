"""Catalogue des épisodes (R&M + épisodes complémentaires), testé au seam applicatif."""
from . import fake_api


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
