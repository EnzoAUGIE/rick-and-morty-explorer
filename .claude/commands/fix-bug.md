---
description: Corrige un bug avec un test de non-régression (testeur → développeur → relecteur)
argument-hint: <description du bug, message d'erreur ou issue>
---

Bug signalé : **$ARGUMENTS**

1. Crée une branche `fix/<slug>`.
2. **Testeur** → délègue à l'agent `testeur` : il écrit d'abord un test qui **reproduit** le bug (il doit échouer) et le documente dans `TEST_REPORT.md`, avec la cause probable.
3. **Développeur** → délègue à l'agent `developpeur` : il corrige le code jusqu'à ce que ce test passe, sans casser les autres. Commit `fix: ...`.
4. **Testeur** → relance toute la suite. Si c'est rouge, renvoie au développeur (2 boucles maximum).
5. **Relecteur** → `REVIEW.md`.
6. Rapport final : cause racine en 1 phrase, correctif en 1 phrase, statut des tests, verdict.

Ne fais jamais `git push`.
