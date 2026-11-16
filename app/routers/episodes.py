from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse

from ..catalogue import Catalogue, EpisodeMoved
from ..client import RickMortyClient
from ..templating import get_catalogue, get_client, templates

router = APIRouter(prefix="/episodes", tags=["épisodes"])


@router.get("")
async def list_episodes(
    request: Request,
    page: int = Query(1, ge=1),
    name: str = "",
    season: str = "",
    catalogue: Catalogue = Depends(get_catalogue),
):
    data = await catalogue.list(page, name=name, season=int(season) if season.isdigit() else None)
    return templates.TemplateResponse(
        request, "episodes/list.html",
        {"theme": "episodes", "page": data, "name": name, "season": season,
         "filters": {"name": name, "season": season},
         "seasons": await catalogue.seasons(),
         "tmdb": any(e.uses_tmdb for e in data.results)},
    )


@router.get("/{episode_id}")
async def episode_detail(
    request: Request,
    episode_id: int,
    catalogue: Catalogue = Depends(get_catalogue),
    client: RickMortyClient = Depends(get_client),
):
    try:
        episode = await catalogue.get(episode_id)
    except EpisodeMoved as moved:  # ADR-0001 : R&M sert maintenant ce code
        return RedirectResponse(f"/episodes/{moved.episode_id}", status_code=301)
    characters = await client.get_many("character", episode.character_ids)
    # Lieux apparaissant dans l'épisode = lieux actuels des personnages présents
    loc_ids = {c.location.id for c in characters if c.location.id}
    locations = await client.get_many("location", sorted(loc_ids))
    season_eps = await catalogue.same_season(episode)
    return templates.TemplateResponse(
        request, "episodes/detail.html",
        {"theme": "episodes", "ep": episode, "characters": characters,
         "locations": locations, "pos": await catalogue.locate(episode),
         "season_eps": season_eps,
         "tmdb": episode.uses_tmdb or any(e.uses_tmdb for e in season_eps)},
    )
