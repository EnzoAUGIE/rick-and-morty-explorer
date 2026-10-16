Contexte : app FastAPI + Jinja2 "Rick & Morty Explorer" (lis d'abord README.md) qui affiche les
données de https://rickandmortyapi.com. Elle a été développée SANS accès réseau, contre une fausse
API (tests/fake_api.py). Ta mission : la valider et l'ajuster sur les VRAIES API depuis ce Mac.
Le dépôt git est propre et poussé sur GitHub ; travaille par petits commits.

Règles :
- Ne change ni l'architecture ni le design. Corrige le minimum, explique pourquoi AVANT de modifier.
- La clé TMDB est dans la variable d'environnement TMDB_API_KEY. Ne l'affiche jamais, ne l'écris
  dans aucun fichier, ne la commite jamais. Vérifie seulement sa présence : echo ${TMDB_API_KEY:+définie}
- Chaque correction = un test pytest ajouté + un commit au message clair. Ne pousse PAS sans me demander.

1. Installation et tests
   python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt && pytest -q

2. API Rick & Morty : fiabilité
   Lance uvicorn app.main:app --port 8000 en arrière-plan, puis avec curl :
   /characters?page=1 à 42, /locations?page=1 à 7, /episodes?page=1 à 3, /episodes/1 à 51,
   /media/character/1.jpeg à 100.
   Relève dans les logs les lignes "WARNING app.client" / "ERROR app.client" et donne-moi des chiffres :
   nb de requêtes, code HTTP des échecs (429 ? 5xx ? timeout ?), présence de Retry-After,
   nb d'échecs rattrapés par les nouvelles tentatives, nb de pages 503 finales.
   Si des 503 restent, ajuste app/client.py ou app/config.py (essais, backoff, ou un
   asyncio.Semaphore limitant les requêtes simultanées vers l'API).

3. Modèles
   Vérifie qu'aucune ValidationError n'apparaît sur la totalité des personnages, lieux et épisodes
   (champs de la vraie API vs app/models.py).

4. Liens entre pages
   Vérifie /characters/1 (« Partage le plus d'épisodes avec », « Autres versions de Rick Sanchez »),
   /locations/3 (épisodes des résidents), /locations/1 (lieux de la même dimension),
   /episodes/12 (bandeau saison 2), et chaque lien filtrable (statut, espèce, type, genre, type de lieu,
   dimension, saison). Signale tout lien menant à une liste vide ou à une 404.

5. Images d'épisodes TMDB (app/tmdb.py)
   a. Confirme que la clé est définie et que le log de démarrage indique "Images d'épisodes : TMDB".
   b. Pour les 51 épisodes de l'API (S01E01 → S05E10), vérifie que chacun reçoit une image
      image.tmdb.org : fais un tableau saison / nb d'épisodes API / nb d'images trouvées.
   c. Vérifie que la numérotation TMDB (série 60625) correspond bien aux codes SxxEyy de l'API ;
      s'il y a un décalage sur une saison, corrige le mapping dans app/tmdb.py.
   d. Vérifie qu'une clé invalide (TMDB_API_KEY=xxx dans un second serveur sur le port 8001)
      donne bien la mosaïque de secours sans erreur de page.
   e. Vérifie que la mention d'attribution TMDB s'affiche dans le pied de page des pages épisodes.
   f. Si pertinent : ajoute dans le README une section courte « Activer les images TMDB »
      (sans jamais y mettre de clé).

6. Fin
   pytest -q doit passer entièrement. Vérifie avec git grep que la clé n'apparaît nulle part.
   Résume-moi : problèmes trouvés, corrections (avec les commits), chiffres des étapes 2 et 5,
   puis demande-moi si tu dois pousser.
