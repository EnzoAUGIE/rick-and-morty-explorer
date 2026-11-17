import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app
from app.tmdb import TmdbClient

from . import fake_api, fake_tmdb


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    """Chaque test a son propre cache disque (avatars)."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    return tmp_path / "cache"


@pytest.fixture(autouse=True)
def no_env_tmdb_key(monkeypatch):
    """Hermétique : la vraie TMDB_API_KEY de l'environnement n'est jamais utilisée."""
    monkeypatch.setattr(config, "TMDB_API_KEY", "")


@pytest.fixture(autouse=True)
def clean_call_logs():
    """Journaux des requêtes simulées vides au début de chaque test."""
    fake_api.calls.clear()
    fake_tmdb.calls.clear()


@pytest.fixture
def client():
    fake_api.calls.clear()
    fake_tmdb.calls.clear()
    app = create_app(transport=fake_api.transport, client_options={"backoff": 0},
                     tmdb=TmdbClient(""))  # hermétique : ignore TMDB_API_KEY de l'environnement
    with TestClient(app) as c:
        yield c


@pytest.fixture
def full_client():
    """App avec faux R&M et faux TMDB (clé valide) : catalogue complet."""
    fake_api.calls.clear()
    fake_tmdb.calls.clear()
    app = create_app(transport=fake_api.transport, client_options={"backoff": 0},
                     tmdb=fake_tmdb.client())
    with TestClient(app) as c:
        yield c
