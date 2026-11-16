#!/usr/bin/env bash
# ------------------------------------------------------------------
# parallel.sh — Plusieurs agents développeurs EN PARALLÈLE,
# chacun dans son propre git worktree, sur sa propre branche.
#
# Usage :
#   .claude/scripts/parallel.sh "backend:ajouter l'endpoint POST /users" \
#                               "frontend:créer le formulaire d'inscription" \
#                               "docs:documenter l'API utilisateurs"
#
# Chaque argument est au format  nom-du-lot:description
# Résultat : branches feat/<nom-du-lot>, worktrees dans .claude/worktrees/
# Ensuite : testeur + relecteur sont lancés dans chaque worktree.
#
# Variables optionnelles :
#   BASE_BRANCH=main   PERMISSION_MODE=acceptEdits   NO_REVIEW=1
# Compatible bash 3.2 (macOS) et Linux.
# ------------------------------------------------------------------
set -euo pipefail

if [ $# -lt 1 ]; then
  sed -n '2,20p' "$0"
  exit 1
fi

BASE_BRANCH="${BASE_BRANCH:-main}"
PERMISSION_MODE="${PERMISSION_MODE:-acceptEdits}"
ROOT="$(git rev-parse --show-toplevel)"
WT_DIR="$ROOT/.claude/worktrees"
LOG_DIR="$ROOT/.claude/logs"
mkdir -p "$WT_DIR" "$LOG_DIR"

command -v claude >/dev/null 2>&1 || { echo "❌ 'claude' introuvable." >&2; exit 1; }
git rev-parse --verify "$BASE_BRANCH" >/dev/null 2>&1 || { echo "❌ Branche de base '$BASE_BRANCH' introuvable (essaie BASE_BRANCH=master)." >&2; exit 1; }

PIDS=""
NAMES=""

for spec in "$@"; do
  name="${spec%%:*}"
  desc="${spec#*:}"
  if [ -z "$name" ] || [ "$name" = "$spec" ]; then
    echo "❌ Format invalide : '$spec' (attendu nom:description)" >&2
    exit 1
  fi
  wt="$WT_DIR/$name"
  branch="feat/$name"

  if [ -d "$wt" ]; then
    echo "♻️  Worktree existant réutilisé : $wt"
  else
    git worktree add "$wt" -b "$branch" "$BASE_BRANCH"
  fi

  log="$LOG_DIR/parallel-$name.log"
  echo "🚀 [$name] lancement → $log"
  (
    cd "$wt"
    {
      echo "===== DEV [$name] ====="
      claude -p "Utilise le sous-agent 'developpeur'. Implémente UNIQUEMENT ce lot : $desc. Commence par écrire un mini PLAN.md pour ce lot, puis implémente-le et commite." --permission-mode "$PERMISSION_MODE"
      if [ "${NO_REVIEW:-0}" != "1" ]; then
        echo "===== TEST [$name] ====="
        claude -p "Utilise le sous-agent 'testeur' sur le diff par rapport à $BASE_BRANCH et produis TEST_REPORT.md." --permission-mode "$PERMISSION_MODE"
        echo "===== REVIEW [$name] ====="
        claude -p "Utilise le sous-agent 'relecteur' sur le diff par rapport à $BASE_BRANCH et produis REVIEW.md." --permission-mode "$PERMISSION_MODE"
      fi
    } > "$log" 2>&1
  ) &
  PIDS="$PIDS $!"
  NAMES="$NAMES $name"
done

echo ""
echo "⏳ Agents en cours. Suivi en direct : tail -f $LOG_DIR/parallel-*.log"
FAIL=0
for pid in $PIDS; do
  wait "$pid" || FAIL=1
done

echo ""
echo "=============================================="
echo "🏁 Résultats"
for name in $NAMES; do
  wt="$WT_DIR/$name"
  verdict="?"
  tests="?"
  [ -f "$wt/REVIEW.md" ] && { grep -qE "^VERDICT: (APPROUVE|OK)" "$wt/REVIEW.md" && verdict="✅ approuvé" || verdict="🔁 changements"; }
  [ -f "$wt/TEST_REPORT.md" ] && { grep -q "^STATUT: VERT" "$wt/TEST_REPORT.md" && tests="✅" || tests="❌"; }
  printf "  %-15s branche feat/%-15s tests %s  revue %s\n" "$name" "$name" "$tests" "$verdict"
done
echo ""
echo "Pour merger (après vérification) :"
echo "  git checkout $BASE_BRANCH"
for name in $NAMES; do echo "  git merge --no-ff feat/$name"; done
echo "Pour nettoyer : .claude/scripts/cleanup-worktrees.sh"
echo "=============================================="
exit $FAIL
