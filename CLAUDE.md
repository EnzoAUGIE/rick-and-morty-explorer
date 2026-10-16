## Projet

Rick & Morty Explorer : FastAPI + Jinja2, données de rickandmortyapi.com (voir README.md).

### Commandes
- Tests : `pytest -q` (100 % hors ligne, via `tests/fake_api.py` ; aucun test ne doit toucher le réseau)
- Serveur : `uvicorn app.main:app --reload`

### Règles
- `app/client.py` est le seul point d'accès à l'API Rick & Morty ; les routers ne font pas d'appels HTTP directs.
- Toute correction ou feature s'accompagne d'un test pytest.
- `TMDB_API_KEY` est lue uniquement depuis l'environnement : ne jamais l'afficher, la logger, l'écrire dans un fichier ni la commiter.
- L'API renvoie des 429 (Retry-After 3–10 s) : ne pas multiplier les appels, passer par le cache du client.

## Agent skills

### Issue tracker

Les issues sont suivies dans les GitHub Issues du dépôt (CLI `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Vocabulaire par défaut : `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context : un `CONTEXT.md` et `docs/adr/` à la racine. See `docs/agents/domain.md`.
