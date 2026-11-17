# Rick & Morty Explorer

Site d'exploration de la série Rick & Morty : personnages, lieux et épisodes, avec leurs liens croisés. Les données viennent de l'API Rick & Morty (R&M), complétées par TMDB pour les épisodes que l'API ne contient pas.

## Language

**Épisode**:
Unité de la série, identifiée par son **code**.
_Avoid_: numéro d'épisode seul (ambigu entre saisons)

**Code (d'épisode)**:
Identifiant fonctionnel d'un épisode au format `SxxEyy` (ex. `S06E01`). C'est la clé qui permet de fusionner les deux sources.
_Avoid_: id (réservé à l'identifiant technique utilisé dans les URLs)

**Épisode complémentaire**:
Épisode absent de l'API R&M et fourni par TMDB. Son affichage est partiel : il n'a pas de casting complet, seulement des **invités**.
_Avoid_: épisode TMDB, épisode manquant, épisode externe

**Catalogue**:
Ensemble fusionné des épisodes R&M et des épisodes complémentaires. Pour un même code, l'API R&M l'emporte.
_Avoid_: liste d'épisodes (désigne une page affichée, pas l'ensemble)

**Construction à froid**:
Première construction du **catalogue**, quand aucun catalogue n'est encore en mémoire : elle lit les deux sources, directement ou depuis leurs caches disque.
_Avoid_: démarrage, préchauffage

**Mode dégradé**:
État du **catalogue** servi avec une source absente ou partielle (sans TMDB, TMDB en panne, liste R&M incomplète) : la page s'affiche sans erreur avec ce qui est disponible.
_Avoid_: mode secours, fallback

**Invité**:
Personnage nommé par TMDB pour un épisode complémentaire. Il est **lié** quand son nom correspond à une fiche R&M, sinon il reste du **texte simple**.
_Avoid_: guest star, acteur

**Fiche**:
Page d'un personnage de l'API R&M.
_Avoid_: profil, page personnage
