"""Modèles de données (équivalents de Personnage.java, Lieu.java, Episodes.java).

Pydantic valide le JSON de l'API et expose des propriétés pratiques
(ids extraits des URLs) qui servent à construire les liens croisés.
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, field_validator

T = TypeVar("T")


def id_from_url(url: str | None) -> int | None:
    """'https://rickandmortyapi.com/api/location/3' -> 3 ; '' -> None."""
    if not url:
        return None
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else None


MAIN_CAST = {1, 2, 3, 4, 5}  # Rick, Morty, Summer, Beth, Jerry


def avatar_url(character_id: int) -> str:
    return f"/media/character/{character_id}.jpeg"


class LinkRef(BaseModel):
    """Référence {name, url} utilisée par origin / location d'un personnage."""
    name: str
    url: str = ""

    @property
    def id(self) -> int | None:
        return id_from_url(self.url)


class Character(BaseModel):
    id: int
    name: str
    status: str
    species: str
    type: str = ""
    gender: str
    origin: LinkRef
    location: LinkRef
    image: str
    episode: list[str]
    url: str
    created: str

    @field_validator("origin", "location", mode="before")
    @classmethod
    def _unknown_if_missing(cls, v):
        # Côté serveur, origin/location sont des références MongoDB "populées" :
        # une référence cassée donne null -> on normalise en lieu inconnu.
        return v or {"name": "unknown", "url": ""}

    @property
    def avatar(self) -> str:
        """Avatar servi par notre serveur (cache disque), pas directement par l'API."""
        return avatar_url(self.id)

    @property
    def episode_ids(self) -> list[int]:
        return [i for i in map(id_from_url, self.episode) if i is not None]


class Location(BaseModel):
    id: int
    name: str
    type: str = ""
    dimension: str = ""
    residents: list[str]
    url: str
    created: str

    @property
    def resident_ids(self) -> list[int]:
        return [i for i in map(id_from_url, self.residents) if i is not None]


class Episode(BaseModel):
    id: int
    name: str
    air_date: str
    episode: str  # code type "S01E01"
    characters: list[str]
    url: str
    created: str

    @property
    def character_ids(self) -> list[int]:
        return [i for i in map(id_from_url, self.characters) if i is not None]

    @property
    def season(self) -> int:
        return int(self.episode[1:3]) if self.episode[:1] == "S" else 0

    @property
    def number(self) -> int:
        """'S02E07' -> 7"""
        return int(self.episode[4:6]) if len(self.episode) >= 6 else 0

    @property
    def cover_avatars(self) -> list[str]:
        """4 personnages pour la mosaïque de secours (sans image TMDB).

        Rick, Morty, Summer, Beth et Jerry sont dans presque tous les épisodes :
        on met d'abord les invités, pour que chaque épisode ait une image distincte.
        """
        ids = self.character_ids
        guests = [i for i in ids if i not in MAIN_CAST]
        picks = (guests + [i for i in ids if i in MAIN_CAST])[:4]
        return [avatar_url(i) for i in picks]


class PageInfo(BaseModel):
    count: int = 0
    pages: int = 0
    next: str | None = None
    prev: str | None = None


class Page(BaseModel, Generic[T]):
    """Une page de résultats de l'API (20 éléments max)."""
    info: PageInfo
    results: list[T]
    current: int = 1

    @property
    def has_next(self) -> bool:
        return self.info.next is not None

    @property
    def has_prev(self) -> bool:
        return self.info.prev is not None
