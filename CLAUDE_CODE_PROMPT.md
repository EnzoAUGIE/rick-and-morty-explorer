Contexte : app FastAPI + Jinja2 "rickmorty-py" (voir README.md) qui affiche les données de
https://rickandmortyapi.com. Elle a été développée sans accès réseau, avec une fausse API
(tests/fake_api.py). Ta mission est de la valider et de l'ajuster sur la VRAIE API, depuis ce Mac.

1. Installe et lance les tests :
   python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt && pytest -q
2. Lance le serveur en arrière-plan (uvicorn app.main:app --port 8000), puis enchaîne avec curl :
   /characters?page=1 à 42, /locations?page=1 à 7, /episodes?page=1 à 3, /episodes/1 à 51,
   et les avatars /media/character/1.jpeg à 100.
   Relève dans les logs les lignes "WARNING app.client" / "ERROR app.client" :
   quel code HTTP renvoie l'API quand elle échoue (429 ? 5xx ? timeout ?), à quelle fréquence,
   et si l'en-tête Retry-After est présent. Donne-moi les chiffres (nb de requêtes, nb d'échecs
   avant/après les nouvelles tentatives, nb de pages 503 finales).
3. Si des 503 restent, ajuste le minimum nécessaire dans app/client.py ou app/config.py
   (nombre d'essais, backoff, limite de requêtes simultanées avec un asyncio.Semaphore…).
   Explique pourquoi avant de modifier.
4. Vérifie que les champs renvoyés par la vraie API correspondent aux modèles de app/models.py
   (aucune ValidationError dans les logs), y compris sur tous les lieux et tous les épisodes.
5. Si la variable TMDB_API_KEY est définie, vérifie que /episodes affiche des images
   image.tmdb.org et que S01E01 à S05E10 ont tous une image (sinon liste ceux qui manquent).
6. Vérifie les liens sur la vraie API : /characters/1 (sections « Partage le plus d'épisodes avec »
   et « Autres versions de Rick Sanchez »), /locations/3 (épisodes des résidents), /locations/1
   (lieux de la même dimension), /episodes/12 (bandeau de la saison 2), et un clic sur chaque valeur
   filtrable. Signale tout lien vers une liste vide ou une page 404.
7. Relance pytest -q. Tout doit passer ; ajoute un test pour chaque correction.
Ne change pas l'architecture ni le design. Résume à la fin : problèmes trouvés, corrections, chiffres.
