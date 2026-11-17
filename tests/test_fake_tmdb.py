"""Fidélité du faux TMDB à ce que le code applicatif suppose (hypothèses H1 à H6)."""
import httpx
import pytest

from . import fake_tmdb

BASE = "https://api.themoviedb.org/3"


def test_fake_tmdb_behaviour():
    fake_tmdb.calls.clear()
    with httpx.Client(transport=fake_tmdb.transport(), base_url=BASE) as h:
        ok = {"api_key": fake_tmdb.KEY}
        seasons = [s["season_number"] for s in h.get("/tv/60625", params=ok).json()["seasons"]]
        assert seasons == [0, 1, 6, 7]
        s6 = h.get("/tv/60625/season/6", params=ok).json()["episodes"]
        assert len(s6) == 10 and s6[0]["guest_stars"][0]["character"] == "Rick Sanchez (voice)"

        bad = h.get("/tv/60625", params={"api_key": "mauvaise"})
        assert bad.status_code == 401 and fake_tmdb.KEY not in bad.text
        assert h.get("/tv/60625").status_code == 401

        assert h.get("/tv/60625/season/99", params=ok).status_code == 404

    assert all("?" not in c and fake_tmdb.KEY not in c for c in fake_tmdb.calls)
    assert "/3/tv/60625/season/6" in fake_tmdb.calls


def test_fake_tmdb_failures_are_per_season_and_mutable():
    fail = {7: 429}
    ok = {"api_key": fake_tmdb.KEY}
    with httpx.Client(transport=fake_tmdb.transport(fail=fail), base_url=BASE) as h:
        assert h.get("/tv/60625/season/7", params=ok).status_code == 429
        assert h.get("/tv/60625/season/6", params=ok).status_code == 200
        fail.clear()  # « réparer » TMDB
        assert h.get("/tv/60625/season/7", params=ok).status_code == 200
        fail["show"] = "down"
        with pytest.raises(httpx.ConnectError):
            h.get("/tv/60625", params=ok)
