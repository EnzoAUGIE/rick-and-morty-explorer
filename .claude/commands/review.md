---
description: Lance uniquement le testeur puis le relecteur sur la branche courante
argument-hint: [branche de référence, défaut main]
---

Branche de référence : `$ARGUMENTS`. Si elle est vide, utilise `main`.

1. Délègue à l'agent `testeur` : il écrit les tests manquants pour le diff par rapport à la branche de référence, lance la suite et produit `TEST_REPORT.md`.
2. Délègue à l'agent `relecteur` : il produit `REVIEW.md`.
3. Donne-moi un résumé en 5 lignes maximum : statut des tests, verdict, et les 3 points les plus importants.

Ne modifie pas le code applicatif.
