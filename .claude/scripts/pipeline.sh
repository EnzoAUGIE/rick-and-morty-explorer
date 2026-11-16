#!/usr/bin/env bash
# ------------------------------------------------------------------
# pipeline.sh — Pipeline multi-agents NON interactif (headless)
# architecte → développeur → testeur (boucle) → relecteur
#
# Usage :
#   .claude/scripts/pipeline.sh "ajouter un endpoint /health"
#
# Variables d'environnement optionnelles :
#   MAX_LOOPS=3            nombre max de boucles dev ↔ testeur
#   PERMISSION_MODE=acceptEdits
#   SKIP_BRANCH=1          ne pas créer de branche feat/...
# Compatible bash 3.2 (macOS) et Linux.
# ------------------------------------------------------------------
set -euo pipefail

if [ $# -lt 1 ] || [ -z "${1:-}" ]; then
  echo "Usage : $0 \"<description de la fonctionnalité>\"" >&2
  exit 1
fi

FEATURE="$1"
MAX_LOOPS="${MAX_LOOPS:-3}"
PERMISSION_MODE="${PERMISSION_MODE:-acceptEdits}"
LOG_DIR=".claude/logs"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/pipeline-$STAMP.log"

command -v claude >/dev/null 2>&1 || { echo "❌ Claude Code n'est pas installé (commande 'claude' introuvable)." >&2; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "❌ À lancer depuis un dépôt git." >&2; exit 1; }

mkdir -p "$LOG_DIR"

if [ -n "$(git status --porcelain)" ]; then
  echo "❌ Le dépôt contient des modifications non commitées. Commit ou stash d'abord." >&2
  exit 1
fi

if [ "${SKIP_BRANCH:-0}" != "1" ]; then
  SLUG="$(printf '%s' "$FEATURE" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//; s/-$//' | cut -c1-40)"
  BRANCH="feat/${SLUG:-feature}-$STAMP"
  git checkout -b "$BRANCH"
  echo "🌿 Branche : $BRANCH"
fi

run_agent () {
  # $1 = nom de l'étape (affichage), $2 = prompt
  echo ""
  echo "▶️  $1"
  echo "===== $1 =====" >> "$LOG"
  claude -p "$2" --permission-mode "$PERMISSION_MODE" 2>&1 | tee -a "$LOG"
}

# 1. Architecte
run_agent "Architecte" "Utilise le sous-agent 'architecte' pour produire PLAN.md pour la fonctionnalité suivante : $FEATURE. Ne pose pas de question : documente tes hypothèses dans PLAN.md."

[ -f PLAN.md ] || { echo "❌ PLAN.md n'a pas été créé. Voir $LOG" >&2; exit 1; }

# 2. Développeur
run_agent "Développeur" "Utilise le sous-agent 'developpeur' pour implémenter toutes les tâches de PLAN.md."

# 3. Testeur, en boucle avec le développeur
i=1
while [ "$i" -le "$MAX_LOOPS" ]; do
  run_agent "Testeur (passe $i/$MAX_LOOPS)" "Utilise le sous-agent 'testeur' : écris les tests manquants, lance la suite et produis TEST_REPORT.md."
  if [ -f TEST_REPORT.md ] && grep -q "^STATUT: VERT" TEST_REPORT.md; then
    echo "✅ Tests verts."
    break
  fi
  if [ "$i" -eq "$MAX_LOOPS" ]; then
    echo "⚠️  Tests toujours rouges après $MAX_LOOPS passes. Voir TEST_REPORT.md" >&2
    break
  fi
  run_agent "Développeur (correctifs $i)" "Utilise le sous-agent 'developpeur' pour corriger les échecs décrits dans TEST_REPORT.md."
  i=$((i + 1))
done

# 4. Relecteur
run_agent "Relecteur" "Utilise le sous-agent 'relecteur' pour relire le diff de la branche courante par rapport à main et produire REVIEW.md."

echo ""
echo "=============================================="
echo "🏁 Pipeline terminé"
echo "   Plan    : PLAN.md"
echo "   Tests   : TEST_REPORT.md"
echo "   Revue   : REVIEW.md"
echo "   Log     : $LOG"
echo "   Commits : git log --oneline main..HEAD"
echo "=============================================="
