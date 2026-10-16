"""Liens entre pages : relations directes, par filtre et dérivées."""
import copy
import html as htmllib

from . import fake_api


def page(client, url):
    r = client.get(url)
    assert r.status_code == 200, url
    return htmllib.unescape(r.text)


# ---------- relations par filtre (paramètres documentés)
def test_character_attributes_are_filter_links(client):
    html = page(client, "/characters/1")
    for href in ("/characters?status=Alive", "/characters?species=Human",
                 "/characters?gender=Male"):
        assert f'href="{href}"' in html


def test_character_type_link_is_url_encoded(client):
    html = page(client, "/characters/16")  # type "Parasite, Cyborg"
    assert 'href="/characters?type=Parasite%2C+Cyborg"' in html


def test_species_filter_list(client):
    html = page(client, "/characters?species=Alien")
    assert "Abadango Cluster Princess" in html and "Rick Sanchez" not in html
    assert "Espèce : Alien" in html  # puce de filtre actif


def test_remove_one_filter_keeps_the_others(client):
    html = page(client, "/characters?species=Alien&status=dead")
    assert 'href="/characters?status=dead"' in html   # retirer l'espèce
    assert 'href="/characters?species=Alien"' in html  # retirer le statut


def test_search_form_keeps_hidden_filters(client):
    html = page(client, "/characters?species=Alien")
    assert '<input type="hidden" name="species" value="Alien">' in html


def test_location_type_and_dimension_links(client):
    html = page(client, "/locations/1")
    assert 'href="/locations?type=Planet"' in html
    assert 'href="/locations?dimension=Dimension+C-137"' in html


def test_dimension_filter_list(client):
    html = page(client, "/locations?dimension=Dimension C-137")
    assert "Earth (C-137)" in html and "Citadel of Ricks" not in html


def test_episode_season_link(client):
    assert 'href="/episodes?season=1"' in page(client, "/episodes/3")


# ---------- relations dérivées
def test_co_stars(client):
    html = page(client, "/characters/1")
    assert "Partage le plus d" in html and "en commun" in html
    assert 'href="/characters/2"' in html  # Morty, présent dans les 10 épisodes


def test_other_versions(client, monkeypatch):
    data = copy.deepcopy(fake_api.DATA)
    clone = dict(data["character"][0], id=41, url=f"{fake_api.BASE}/character/41")
    data["character"].append(clone)
    monkeypatch.setattr(fake_api, "DATA", data)
    html = page(client, "/characters/1")
    assert "Autres versions de Rick Sanchez" in html and 'href="/characters/41"' in html


def test_no_versions_section_when_unique(client):
    assert "Autres versions" not in page(client, "/characters/2")


def test_location_episodes_from_residents(client):
    html = page(client, "/locations/3")  # Citadel of Ricks
    assert "Épisodes où apparaissent ses résidents" in html
    assert 'href="/episodes/10"' in html  # S01E10, l'épisode de la Citadelle


def test_same_dimension_locations(client):
    html = page(client, "/locations/1")
    assert "Autres lieux de la dimension" in html
    assert 'href="/locations/5"' in html and 'href="/locations/18"' in html  # Anatomy Park, rêve


def test_unknown_dimension_has_no_neighbours(client):
    assert "Autres lieux de la dimension" not in page(client, "/locations/2")


def test_same_season_strip(client):
    html = page(client, "/episodes/3")
    assert 'class="season-ep current"' in html
    for i in (1, 2, 4, 10):
        assert f'href="/episodes/{i}"' in html
