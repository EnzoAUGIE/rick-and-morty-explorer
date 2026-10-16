"""Configuration centralisée (surchargeable par variables d'environnement)."""
import os
from pathlib import Path

API_BASE_URL: str = os.getenv("RM_API_BASE_URL", "https://rickandmortyapi.com/api")
HTTP_TIMEOUT: float = float(os.getenv("RM_HTTP_TIMEOUT", "10"))
CACHE_TTL_SECONDS: int = int(os.getenv("RM_CACHE_TTL", "3600"))

# Nouvelles tentatives si l'API répond 429 / 5xx / timeout
API_RETRIES: int = int(os.getenv("RM_API_RETRIES", "3"))
API_BACKOFF: float = float(os.getenv("RM_API_BACKOFF", "0.5"))  # 0.5s, 1s, 2s…

# Cache disque (avatars téléchargés une seule fois)
CACHE_DIR: Path = Path(os.getenv("RM_CACHE_DIR", Path(__file__).parent.parent / ".cache"))

# Images d'épisodes (optionnel) : clé API v3 gratuite sur themoviedb.org
TMDB_API_KEY: str = os.getenv("TMDB_API_KEY", "")
TMDB_SHOW_ID: int = int(os.getenv("TMDB_SHOW_ID", "60625"))  # Rick and Morty sur TMDB
