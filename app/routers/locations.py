from fastapi import APIRouter, Depends, Query, Request

from .. import relations
from ..client import RickMortyClient
from ..templating import get_client, templates

router = APIRouter(prefix="/locations", tags=["lieux"])


@router.get("")
async def list_locations(
    request: Request,
    page: int = Query(1, ge=1),
    name: str = "",
    type_: str = Query("", alias="type"),
    dimension: str = "",
    client: RickMortyClient = Depends(get_client),
):
    # Tous les filtres documentés de /api/location
    filters = {"name": name, "type": type_, "dimension": dimension}
    data = await client.list("location", page, **filters)
    return templates.TemplateResponse(
        request, "locations/list.html",
        {"theme": "locations", "page": data, "filters": filters, "name": name},
    )


@router.get("/{location_id}")
async def location_detail(
    request: Request, location_id: int, client: RickMortyClient = Depends(get_client)
):
    location = await client.get("location", location_id)
    residents = await client.get_many("character", location.resident_ids)
    episodes = await relations.location_episodes(client, residents)
    neighbours, neighbours_count = await relations.same_dimension(client, location)
    return templates.TemplateResponse(
        request, "locations/detail.html",
        {"theme": "locations", "loc": location, "residents": residents,
         "episodes": episodes, "neighbours": neighbours,
         "neighbours_count": neighbours_count},
    )
