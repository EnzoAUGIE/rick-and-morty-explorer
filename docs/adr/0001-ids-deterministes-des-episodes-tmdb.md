---
status: accepted
---

# Ids déterministes pour les épisodes absents de l'API Rick & Morty

L'API R&M s'arrête à S05E10 (ids 1–51) ; TMDB fournit les épisodes manquants (tout code `SxxEyy` absent de l'API R&M, saison 0 exclue). Ces épisodes n'ont pas d'id R&M : on leur donne l'id `saison*100 + numéro` (S06E01 → 601) et on garde la route `/episodes/{id}`. Le code `SxxEyy` reste la clé fonctionnelle ; l'id n'en est qu'un encodage stable.

Si R&M ajoute un jour un code déjà servi par TMDB, l'ancienne URL `/episodes/<saison*100+numéro>` répond par une redirection 301 vers l'id R&M de ce même code, et l'API R&M devient la source de ces données.

## Considered Options

- **Continuer la numérotation à 52, dans l'ordre TMDB** : rejeté. Collision avec les futurs ids R&M, et les ids changeraient si TMDB réordonne ou insère un épisode.
- **Routes par code (`/episodes/S06E01`) pour tous les épisodes** : rejeté. Casse les URLs existantes et touche toutes les routes, les liens et les images.

## Consequences

- Le code qui reçoit un id doit savoir si c'est un id R&M (1–51…) ou un id déterministe (≥ 601) ; la redirection 301 impose de retrouver le code `SxxEyy` depuis l'id, puis de le chercher côté R&M.
- Une saison de plus de 99 épisodes ferait collisionner le schéma (hors sujet pour cette série).
