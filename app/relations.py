"""Relations entre personnages, lieux et épisodes.

Relations DIRECTES (champs de l'API, cf. documentation) :
  personnage.origin / .location -> lieu     personnage.episode -> épisodes
  lieu.residents -> personnages             épisode.characters -> personnages

Relations par FILTRE (paramètres de recherche documentés) :
  statut, espèce, type, genre (personnages) ; type, dimension (lieux) ;
  code d'épisode -> saison (épisodes). Construites dans les templates (filter_url).

Relations DÉRIVÉES (calculées ici en croisant les données) :
  - autres versions d'un personnage (même nom, autres dimensions) ;
  - co-vedettes (personnages qui partagent le plus d'épisodes) ;
  - épisodes où apparaissent les résidents d'un lieu ;
  - autres lieux de la même dimension ;
  - autres épisodes de la même saison.
Chaque fonction coûte au plus 1 requête (groupée) en plus de ce que la page charge déjà.
"""
from __future__ import annotations

from collections import Counter

from .client import RickMortyClient
from .models import Character, Episode, Location

UNKNOWN = {"", "unknown"}


async def other_versions(client: RickMortyClient, c: Character, limit: int = 12):
    """Même nom exact dans d'autres dimensions (ex. les nombreux « Rick Sanchez »)."""
    page = await client.list("character", 1, name=c.name)
    same = [x for x in page.results if x.name.lower() == c.name.lower() and x.id != c.id]
    # count : l'API filtre en "contient" -> total approximatif si plus d'une page
    return same[:limit], max(page.info.count - 1, len(same))


async def co_stars(client: RickMortyClient, c: Character, episodes: list[Episode],
                   limit: int = 12) -> list[tuple[Character, int]]:
    """Personnages les plus souvent présents dans les mêmes épisodes."""
    counts = Counter(i for ep in episodes for i in ep.character_ids if i != c.id)
    top = [i for i, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]
    chars = {x.id: x for x in await client.get_many("character", top)}
    return [(chars[i], counts[i]) for i in top if i in chars]


async def location_episodes(client: RickMortyClient,
                            residents: list[Character]) -> list[tuple[Episode, int]]:
    """Épisodes où apparaît au moins un résident, avec le nombre de résidents présents."""
    counts = Counter(i for r in residents for i in r.episode_ids)
    eps = await client.get_many("episode", list(counts))
    return [(e, counts[e.id]) for e in sorted(eps, key=lambda e: e.id)]


async def same_dimension(client: RickMortyClient, loc: Location, limit: int = 8):
    if loc.dimension in UNKNOWN:
        return [], 0
    page = await client.list("location", 1, dimension=loc.dimension)
    others = [x for x in page.results if x.id != loc.id and x.dimension == loc.dimension]
    return others[:limit], max(page.info.count - 1, len(others))


async def same_season(client: RickMortyClient, ep: Episode) -> list[Episode]:
    if not ep.season:
        return []
    page = await client.list("episode", 1, episode=f"S{ep.season:02d}")
    return page.results
