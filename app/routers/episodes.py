from fastapi import APIRouter, Depends, Query, Request

from ..client import RickMortyClient
from ..catalogue import Catalogue
from ..templating import get_catalogue, get_client, get_tmdb, templates
from ..tmdb import TmdbClient

router = APIRouter(prefix="/episodes", tags=["épisodes"])


@router.get("")
async def list_episodes(
    request: Request,
    page: int = Query(1, ge=1),
    name: str = "",
    season: str = "",
    catalogue: Catalogue = Depends(get_catalogue),
    tmdb: TmdbClient = Depends(get_tmdb),
):
    data = await catalogue.list(page, name=name, season=int(season) if season.isdigit() else None)
    stills = await tmdb.stills(data.results)
    return templates.TemplateResponse(
        request, "episodes/list.html",
        {"theme": "episodes", "page": data, "name": name, "season": season,
         "filters": {"name": name, "season": season},
         "seasons": await catalogue.seasons(),
         "stills": stills, "tmdb": bool(stills)},
    )


@router.get("/{episode_id}")
async def episode_detail(
    request: Request,
    episode_id: int,
    catalogue: Catalogue = Depends(get_catalogue),
    client: RickMortyClient = Depends(get_client),
    tmdb: TmdbClient = Depends(get_tmdb),
):
    episode = await catalogue.get(episode_id)
    characters = await client.get_many("character", episode.character_ids)
    # Lieux apparaissant dans l'épisode = lieux actuels des personnages présents
    loc_ids = {c.location.id for c in characters if c.location.id}
    locations = await client.get_many("location", sorted(loc_ids))
    season_eps = await catalogue.same_season(episode)
    stills = await tmdb.stills([episode, *season_eps])
    return templates.TemplateResponse(
        request, "episodes/detail.html",
        {"theme": "episodes", "ep": episode, "characters": characters,
         "locations": locations, "pos": await catalogue.locate(episode),
         "season_eps": season_eps, "stills": stills, "tmdb": bool(stills)},
    )
