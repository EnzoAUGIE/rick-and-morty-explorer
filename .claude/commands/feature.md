---
description: Pipeline complet architecte → développeur → testeur → relecteur pour une nouvelle fonctionnalité
argument-hint: <description de la fonctionnalité>
---

Tu es l'**orchestrateur** de l'équipe. Tu ne codes pas toi-même : tu délègues à chaque sous-agent et tu fais circuler les fichiers de coordination (`PLAN.md`, `TEST_REPORT.md`, `REVIEW.md`).

Fonctionnalité demandée : **$ARGUMENTS**

## Préparation
1. Vérifie que le dépôt git est propre (`git status`). S'il ne l'est pas, arrête-toi et préviens-moi.
2. Crée une branche : `git checkout -b feat/<slug-court-de-la-demande>`.

## Workflow obligatoire
1. **Architecte** → délègue à l'agent `architecte` pour produire `PLAN.md`.
   Montre-moi un résumé du plan (objectif + liste des tâches) puis **continue sans attendre**, sauf si le plan contient une section « Hypothèses » qui change fortement le périmètre : dans ce cas, demande-moi confirmation.
2. **Développeur** → délègue à l'agent `developpeur` pour implémenter toutes les tâches de `PLAN.md`.
3. **Testeur** → délègue à l'agent `testeur`. Il produit `TEST_REPORT.md`.
   - Si `TEST_REPORT.md` contient `STATUT: ROUGE` : renvoie au `developpeur` avec `TEST_REPORT.md`, puis relance le `testeur`. **Maximum 3 boucles.** Au-delà, arrête-toi et fais-moi un rapport.
4. **Relecteur** → délègue à l'agent `relecteur`. Il produit `REVIEW.md`.
   - Si `REVIEW.md` contient `VERDICT: CHANGEMENTS` avec des points 🔴 bloquants : renvoie au `developpeur`, puis repasse par `testeur` et `relecteur`. **Maximum 2 boucles.**

## Rapport final (format court)
- Branche : ...
- Tâches réalisées : x/y
- Tests : ✅/❌ (n passés / n échoués)
- Revue : verdict + nombre de points par niveau
- Commandes pour finaliser :
  ```bash
  git log --oneline main..HEAD
  git checkout main && git merge --no-ff feat/<slug>
  ```

Ne fais jamais `git push` ni de merge toi-même.
