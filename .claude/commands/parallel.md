---
description: Découpe une demande en sous-fonctionnalités indépendantes et les fait développer en parallèle dans des git worktrees isolés
argument-hint: <description globale>
---

Demande globale : **$ARGUMENTS**

1. Délègue à l'agent `architecte` : il produit `PLAN.md` en regroupant les tâches en **lots indépendants**, c'est-à-dire des lots qui ne modifient pas les mêmes fichiers. 4 lots maximum. Chaque lot reçoit un nom court (ex. `backend-api`, `frontend-form`).
2. Montre-moi les lots et les fichiers touchés par chacun. **Attends ma validation** avant de continuer.
3. Pour chaque lot, en **parallèle** : lance un agent `developpeur` **isolé dans son propre worktree git** (isolation worktree), sur une branche `feat/<nom-du-lot>`, avec pour consigne de n'implémenter que les tâches de son lot.
4. Quand tous les lots sont terminés, lance un agent `testeur` puis un agent `relecteur` sur chaque branche (en parallèle si possible).
5. Rapport final : un tableau (lot | branche | tests | verdict), puis l'ordre de merge recommandé et les commandes :
   ```bash
   git checkout main
   git merge --no-ff feat/<lot1>
   git merge --no-ff feat/<lot2>
   ```

Ne merge rien toi-même et ne fais jamais `git push`.
