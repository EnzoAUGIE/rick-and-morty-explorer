from fastapi import APIRouter, Depends, Query, Request

from .. import relations
from ..client import RickMortyClient
from ..templating import get_client, get_tmdb, templates
from ..tmdb import TmdbClient

router = APIRouter(prefix="/episodes", tags=["épisodes"])


@router.get("")
async def list_episodes(
    request: Request,
    page: int = Query(1, ge=1),
    name: str = "",
    season: str = "",
    client: RickMortyClient = Depends(get_client),
    tmdb: TmdbClient = Depends(get_tmdb),
):
    # L'API filtre par code d'épisode : "S02" renvoie toute la saison 2
    code = f"S{int(season):02d}" if season.isdigit() else ""
    data = await client.list("episode", page, name=name, episode=code)
    stills = await tmdb.stills(data.results)
    return templates.TemplateResponse(
        request, "episodes/list.html",
        {"theme": "episodes", "page": data, "name": name, "season": season,
         "filters": {"name": name, "season": season},
         "stills": stills, "tmdb": bool(stills)},
    )


@router.get("/{episode_id}")
async def episode_detail(
    request: Request,
    episode_id: int,
    client: RickMortyClient = Depends(get_client),
    tmdb: TmdbClient = Depends(get_tmdb),
):
    episode = await client.get("episode", episode_id)
    characters = await client.get_many("character", episode.character_ids)
    # Lieux apparaissant dans l'épisode = lieux actuels des personnages présents
    loc_ids = {c.location.id for c in characters if c.location.id}
    locations = await client.get_many("location", sorted(loc_ids))
    total = (await client.list("episode")).info.count  # en cache après le 1er appel
    season_eps = await relations.same_season(client, episode)
    stills = await tmdb.stills([episode, *season_eps])
    return templates.TemplateResponse(
        request, "episodes/detail.html",
        {"theme": "episodes", "ep": episode, "characters": characters,
         "locations": locations, "total": total, "season_eps": season_eps,
         "stills": stills, "tmdb": bool(stills)},
    )
