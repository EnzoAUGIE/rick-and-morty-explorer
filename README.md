# Rick & Morty Explorer (Python)

Réécriture en **Python / FastAPI + Jinja2** de l'app Java Swing `RickAndMorty` (2023).
Les données viennent de l'API publique https://rickandmortyapi.com.

## Lancer

```bash
cd rickmorty-py
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
# -> http://127.0.0.1:8000
```

Tests (hors ligne, avec une fausse API) :

```bash
pytest -q
```

## Architecture

```
app/
├── main.py          # create_app() : routes, fichiers statiques, pages d'erreur 404/503
├── config.py        # URL de l'API, timeout, durée du cache (variables d'env RM_*)
├── client.py        # RickMortyClient : appels HTTP async, cache, requêtes groupées
├── models.py        # Character / Location / Episode (Pydantic) + id_from_url()
├── templating.py    # Jinja2 partagé + dépendances get_client() / get_tmdb()
├── relations.py     # relations dérivées (versions, co-vedettes, épisodes d'un lieu…)
├── illustrations.py # SVG générés pour les lieux (selon le type, couleurs tirées du nom)
├── tmdb.py          # images d'épisodes TMDB (optionnel, si TMDB_API_KEY)
├── routers/         # 1 fichier par catégorie : liste + détail
│   ├── home.py  characters.py  locations.py  episodes.py
│   └── media.py     # /media/character/{id}.jpeg : avatars en cache disque
├── templates/       # base.html, home.html, _macros.html, <catégorie>/{list,detail}.html
└── static/          # css/style.css, js/app.js, img/ (images d'origine du projet Java)
tests/
├── fixtures/api_sample.json  # 40 persos, 20 lieux, 10 épisodes (dump de test officiel)
├── fake_api.py      # API simulée, fidèle au serveur Node (httpx.MockTransport)
├── test_app.py      # pages, filtres, pagination, liens croisés, 404/503, cache
├── test_resilience_images.py  # nouvelles tentatives, cache périmé, avatars, SVG, TMDB
└── test_relations.py          # liens par filtre et relations dérivées
```

Flux d'une requête : `navigateur → router → RickMortyClient → API (ou cache) → modèle Pydantic → template Jinja2 → HTML`.

## Liens entre les pages (d'après la documentation de l'API)

**Relations directes** (champs renvoyés par l'API)

| Depuis | Champ | Vers |
|---|---|---|
| Personnage | `origin`, `location` | Lieu (origine, dernier lieu connu) |
| Personnage | `episode[]` | Épisodes où il apparaît |
| Lieu | `residents[]` | Personnages |
| Épisode | `characters[]` | Personnages |

**Relations par filtre** (chaque valeur cliquable ouvre la liste filtrée, filtres actifs retirables)

| Page | Valeur cliquable | Lien |
|---|---|---|
| Personnage | statut, espèce, type, genre | `/characters?status=…` `species=…` `type=…` `gender=…` |
| Lieu | type, dimension | `/locations?type=…` `dimension=…` |
| Épisode | saison (tirée du code `S01E03`) | `/episodes?season=1` |

**Relations dérivées** (calculées dans `app/relations.py`, 1 requête groupée chacune)

| Page | Section | Calcul |
|---|---|---|
| Personnage | Autres versions | filtre `name` = même nom exact (ex. tous les « Rick Sanchez ») |
| Personnage | Partage le plus d'épisodes avec | comptage des personnages de ses épisodes |
| Lieu | Épisodes où apparaissent ses résidents | union des épisodes des résidents |
| Lieu | Autres lieux de la même dimension | filtre `dimension` |
| Épisode | Bandeau de la saison | filtre `episode=S01` |
| Épisode | Lieux liés | dernier lieu connu de ses personnages |

Limite connue de l'API : les filtres cherchent un texte *contenu* (insensible à la casse), pas une
valeur exacte. `species=Human` ramène donc aussi les `Humanoid`. L'API ne propose pas de filtre
« personnages nés dans ce lieu » (`origin`), d'où son absence.

## Fiabilité (API qui ne répond pas toujours)

- **Nouvelles tentatives** sur 429 / 5xx / timeout : 3 essais de plus, attente 0,5 s → 1 s → 2 s,
  en respectant l'en-tête `Retry-After`. Chaque essai est écrit dans le terminal
  (`WARNING app.client - API /character -> HTTP 429, nouvel essai 1/3…`) : tu vois la vraie cause.
- **Cache périmé en secours** : si l'API tombe, on ressert la dernière réponse connue.
- **Avatars en cache disque** (`.cache/avatars/`) : téléchargés une seule fois par notre serveur,
  au lieu de ~20 requêtes du navigateur vers l'API à chaque page. Si un avatar échoue :
  image de secours, et nouvel essai à la visite suivante.

## Images

| Catégorie | Source |
|---|---|
| Personnages | avatars de l'API, en cache disque |
| Lieux | illustration SVG générée (planète, amas, station, dimension, micro-univers, lieu « terrestre ») |
| Épisodes | capture officielle TMDB si `TMDB_API_KEY` est défini, sinon mosaïque de 4 personnages invités |

Activer les images TMDB (clé gratuite : themoviedb.org → Paramètres → API → « Clé d'API (v3) ») :

```bash
export TMDB_API_KEY="ta_cle_v3"
uvicorn app.main:app --reload
```

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `RM_API_RETRIES` | 3 | nouvelles tentatives par requête |
| `RM_API_BACKOFF` | 0.5 | première attente (s), doublée à chaque essai |
| `RM_HTTP_TIMEOUT` | 10 | timeout (s) |
| `RM_CACHE_TTL` | 3600 | durée du cache mémoire (s) |
| `RM_CACHE_DIR` | `.cache` | dossier du cache disque |
| `TMDB_API_KEY` | — | active les images d'épisodes |

## Routes

| URL | Page |
|---|---|
| `/` | Accueil, 3 portails (Personnages, Lieux, Épisodes) |
| `/characters?name=&status=&page=` | Liste des personnages (recherche + filtre statut) |
| `/characters/{id}` | Fiche → liens vers origine, dernier lieu, épisodes |
| `/locations?name=&page=` | Liste des lieux |
| `/locations/{id}` | Fiche → liens vers les résidents |
| `/episodes?name=&season=&page=` | Liste des épisodes (filtre saison) |
| `/episodes/{id}` | Fiche → liens vers personnages, lieux liés, épisode préc./suiv. |
| `/media/character/{id}.jpeg` | Avatar (cache disque) |

## Différences avec la version Java

| Java (Swing) | Python (web) |
|---|---|
| `JComboBox` pour choisir la catégorie | 3 boutons « portail » sur la page d'accueil |
| Téléchargement de toutes les pages au clic (pagination cassée : `get("info.next")` ne lit pas un champ imbriqué, donc seule la page 1 était chargée) | Pagination côté API, 20 éléments par page, + recherche et filtres |
| Clic = ouverture du JSON brut dans le navigateur | Clic = fiche HTML avec liens vers les entités liées |
| Classes `Personnage`, `Lieu`, `Episodes` jamais utilisées | Modèles Pydantic réellement utilisés pour valider le JSON |
| Chemins `src/images/...` (dossier réel : `Images/`, et `.jpg` vs `.jpeg`) | Fichiers statiques servis par FastAPI |
| Dialogue de fermeture (Rick-ornichon / Wubba Lubba Dub Dub) | Conservé : bouton « Quitter » en bas de page |

## Références

- Documentation officielle : https://rickandmortyapi.com/documentation
- Code du serveur de l'API (Node/Express/MongoDB) : https://github.com/EnzoAUGIE/rick-and-morty-api
  - `test/data/*.bson` → converti en `tests/fixtures/api_sample.json`
  - `routes/middlewares.js` et `handlers/operations.js` → comportement reproduit par `tests/fake_api.py`
    (20 par page, 404 au-delà de la dernière page, ids `1,2,3` ou `[1,2,3]`, filtres regex)
- Wrapper Python `ramapi` : https://github.com/curiousrohan/ramapi — étudié mais non utilisé
  (synchrone, sans cache ni requêtes groupées, paramètres non encodés) ; `app/client.py` le remplace.
