"""Instance Jinja2 partagée + dépendance pour récupérer le client API."""
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .client import RickMortyClient
from .illustrations import location_art

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

STATUS_FR = {"Alive": "Vivant", "Dead": "Mort", "unknown": "Inconnu"}
templates.env.filters["status_fr"] = lambda s: STATUS_FR.get(s, s)
templates.env.globals["location_art"] = location_art


def get_client(request: Request) -> RickMortyClient:
    return request.app.state.client


def get_tmdb(request: Request):
    return request.app.state.tmdb
