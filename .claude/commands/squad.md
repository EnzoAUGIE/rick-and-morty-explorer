---
description: Le chef de projet propose l'équipe (nombre d'agents, rôles, modèles recommandés), tu valides ou modifies, puis l'équipe exécute
argument-hint: <description de ce que tu veux réaliser>
---

Tu es l'**orchestrateur**. Tu ne codes pas toi-même.

Demande : **$ARGUMENTS**

## Phase 1 — Proposition (aucune modification du code)
1. Vérifie que le dépôt git est propre (`git status`). S'il ne l'est pas, arrête-toi et préviens-moi.
2. Délègue à l'agent `chef-de-projet` : il produit `TEAM.md`.
3. Affiche-moi le contenu de `TEAM.md` : taille, mode, tableau de l'équipe recommandée, alternative économique et rôles écartés.
4. Demande-moi de choisir :
   - **Valider** l'équipe recommandée
   - **Alternative économique**
   - **Modifier** : je te dis quoi changer (ex. « passe le relecteur en sonnet », « ajoute un documentaliste », « pas de parallèle »). Mets alors `TEAM.md` à jour, réaffiche le tableau et redemande-moi.
   - **Annuler**

**N'avance pas tant que je n'ai pas validé.**

## Phase 2 — Exécution de l'équipe validée
1. Crée une branche `feat/<slug>`.
2. Suis l'ordre de la colonne « Étape » de `TEAM.md`.
3. Pour chaque rôle :
   - **Rôle permanent** : délègue à l'agent du même nom, avec le **modèle indiqué dans TEAM.md**. S'il diffère de celui du fichier de l'agent, passe-le en surcharge de modèle au moment de la délégation.
   - **Rôle ad hoc** : délègue à un agent généraliste avec le modèle indiqué. Donne-lui comme consigne : « Tu es <rôle>. » suivi de la section « Mission des rôles ad hoc » de `TEAM.md`, plus le contenu de `CLAUDE.md`. Interdis-lui `git push` et toute modification hors de sa mission. S'il existe un skill pertinent dans `.claude/skills/` (ex. `code-review` pour `securite`), dis-lui de le lire et de l'appliquer.
   - **Étapes marquées parallèle** : lance ces agents **en même temps**, chaque développeur **isolé dans son propre worktree git**, sur une branche `feat/<lot>`, limité aux fichiers de son lot.
4. Boucles de correction (comme `/feature`) :
   - `TEST_REPORT.md` contient `STATUT: ROUGE` → developpeur puis testeur, **3 boucles maximum** ;
   - `REVIEW.md` contient `VERDICT: CHANGEMENTS` avec des points 🔴 → developpeur → testeur → relecteur, **2 boucles maximum** ;
   - un rôle `securite` remonte un point critique → traité comme un point 🔴 bloquant.
5. Si un agent échoue deux fois de suite, arrête-toi et fais-moi un rapport plutôt que de continuer.

## Phase 3 — Rapport final
- Équipe réellement utilisée : tableau rôle | modèle | statut
- Branches créées et ordre de merge recommandé
- Tests : ✅/❌ ; revue : verdict et nombre de points par niveau
- Commandes pour finaliser (`git log`, `git merge --no-ff ...`)
- Si un rôle ad hoc a été utile, propose-moi de le transformer en agent permanent dans `.claude/agents/<role>.md`. Ne le crée que si j'accepte, et préviens-moi qu'il faudra relancer `claude` pour qu'il soit chargé.

Ne fais jamais `git push` ni de merge toi-même.
