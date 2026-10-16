"""Avatars servis par notre serveur, avec cache disque.

Avant : le navigateur chargeait ~20 avatars directement chez rickandmortyapi.com
à chaque page, et certains échouaient (personnages "sans image").
Maintenant : chaque avatar est téléchargé UNE fois (avec nouvelles tentatives),
stocké dans .cache/avatars/, puis servi localement. En cas d'échec, on renvoie
une image de secours sans la mettre en cache, pour réessayer à la prochaine visite.
"""
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from .. import config
from ..client import ApiUnavailableError, NotFoundError, RickMortyClient
from ..templating import get_client

router = APIRouter(prefix="/media", include_in_schema=False)
PLACEHOLDER = Path(__file__).parent.parent / "static" / "img" / "placeholder.svg"


@router.get("/character/{character_id}.jpeg")
async def avatar(character_id: int, client: RickMortyClient = Depends(get_client)):
    path = config.CACHE_DIR / "avatars" / f"{character_id}.jpeg"
    if not path.exists():
        try:
            data = await client.get_bytes(
                f"{config.API_BASE_URL}/character/avatar/{character_id}.jpeg")
        except (NotFoundError, ApiUnavailableError):
            return FileResponse(PLACEHOLDER, media_type="image/svg+xml",
                                headers={"Cache-Control": "no-store"})
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)  # écriture atomique : jamais de fichier à moitié écrit
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=604800"})
