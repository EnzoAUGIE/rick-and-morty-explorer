import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app
from app.tmdb import TmdbClient

from . import fake_api


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    """Chaque test a son propre cache disque (avatars)."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    return tmp_path / "cache"


@pytest.fixture
def client():
    fake_api.calls.clear()
    app = create_app(transport=fake_api.transport, client_options={"backoff": 0},
                     tmdb=TmdbClient(""))  # hermétique : ignore TMDB_API_KEY de l'environnement
    with TestClient(app) as c:
        yield c
