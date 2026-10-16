"""Point d'entrée FastAPI (équivalent de Main.java, sans la logique métier)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .client import ApiUnavailableError, NotFoundError, RickMortyClient
from .routers import characters, episodes, home, locations, media
from .tmdb import TmdbClient
from .templating import templates

BASE_DIR = Path(__file__).parent

# Les avertissements du client (nouvelles tentatives, vrai code HTTP) s'affichent
# dans le terminal uvicorn, à côté des lignes "GET /... 200 OK".
logging.basicConfig(level=logging.INFO, format="%(levelname)-9s %(name)s - %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # pas une ligne par requête sortante


def create_app(
    transport: httpx.AsyncBaseTransport | None = None,
    *,
    client_options: dict | None = None,
    tmdb: TmdbClient | None = None,
) -> FastAPI:
    """Fabrique d'application.

    En test : `transport` injecte une fausse API, `client_options` règle par
    exemple backoff=0, `tmdb` injecte un faux client TMDB.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.client = RickMortyClient(transport=transport, **(client_options or {}))
        app.state.tmdb = tmdb or TmdbClient()
        logging.getLogger("app").info(
            "Images d'épisodes : %s", "TMDB" if app.state.tmdb.enabled
            else "mosaïque de personnages (définir TMDB_API_KEY pour les vraies images)")
        yield
        await app.state.client.aclose()
        await app.state.tmdb.aclose()

    app = FastAPI(title="Rick & Morty Explorer", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    for r in (home.router, characters.router, locations.router, episodes.router, media.router):
        app.include_router(r)

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError):
        return templates.TemplateResponse(
            request, "error.html",
            {"theme": "home", "title": "Introuvable",
             "message": "Cette dimension n'existe pas (encore)."},
            status_code=404,
        )

    @app.exception_handler(ApiUnavailableError)
    async def api_down(request: Request, exc: ApiUnavailableError):
        return templates.TemplateResponse(
            request, "error.html",
            {"theme": "home", "title": "API indisponible",
             "message": "Le portail vers rickandmortyapi.com est fermé. Réessaie dans quelques secondes.",
             "detail": f"Dernière erreur après plusieurs essais : {exc}"},
            status_code=503,
        )

    return app


app = create_app()
