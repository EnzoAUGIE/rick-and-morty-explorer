#!/usr/bin/env bash
# ------------------------------------------------------------------
# cleanup-worktrees.sh — Supprime les worktrees créés par parallel.sh
# Les BRANCHES sont conservées (supprime-les avec : git branch -d feat/<nom>)
#
# Usage : .claude/scripts/cleanup-worktrees.sh [--force]
# ------------------------------------------------------------------
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
WT_DIR="$ROOT/.claude/worktrees"
FORCE=""
[ "${1:-}" = "--force" ] && FORCE="--force"

[ -d "$WT_DIR" ] || { echo "Aucun worktree à nettoyer."; exit 0; }

for wt in "$WT_DIR"/*; do
  [ -d "$wt" ] || continue
  echo "🧹 Suppression du worktree $wt"
  git worktree remove $FORCE "$wt" || echo "   ⚠️  Échec (modifs non commitées ?). Relance avec --force si tu es sûr."
done
git worktree prune
echo "✅ Terminé. Branches restantes :"
git branch --list 'feat/*'
