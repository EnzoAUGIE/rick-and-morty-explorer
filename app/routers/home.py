from fastapi import APIRouter, Request

from ..templating import templates

router = APIRouter()


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "home.html", {"theme": "home"})
