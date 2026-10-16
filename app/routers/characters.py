from fastapi import APIRouter, Depends, Query, Request

from .. import relations
from ..client import RickMortyClient
from ..templating import get_client, templates

router = APIRouter(prefix="/characters", tags=["personnages"])


@router.get("")
async def list_characters(
    request: Request,
    page: int = Query(1, ge=1),
    name: str = "",
    status: str = "",
    species: str = "",
    type_: str = Query("", alias="type"),
    gender: str = "",
    client: RickMortyClient = Depends(get_client),
):
    # Tous les filtres documentés de /api/character
    filters = {"name": name, "status": status, "species": species,
               "type": type_, "gender": gender}
    data = await client.list("character", page, **filters)
    return templates.TemplateResponse(
        request, "characters/list.html",
        {"theme": "characters", "page": data, "filters": filters,
         "name": name, "status": status},
    )


@router.get("/{character_id}")
async def character_detail(
    request: Request, character_id: int, client: RickMortyClient = Depends(get_client)
):
    character = await client.get("character", character_id)
    episodes = await client.get_many("episode", character.episode_ids)
    versions, versions_count = await relations.other_versions(client, character)
    co_stars = await relations.co_stars(client, character, episodes)
    return templates.TemplateResponse(
        request, "characters/detail.html",
        {"theme": "characters", "c": character, "episodes": episodes,
         "versions": versions, "versions_count": versions_count, "co_stars": co_stars},
    )
