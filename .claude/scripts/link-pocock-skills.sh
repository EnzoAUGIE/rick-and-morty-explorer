#!/usr/bin/env bash
# ------------------------------------------------------------------
# link-pocock-skills.sh — Branche les skills de Matt Pocock sur les agents
#
# Les sous-agents Claude Code N'HÉRITENT PAS des skills de la session :
# il faut les lister dans le champ `skills:` de leur frontmatter, qui
# précharge le contenu du skill au démarrage de l'agent.
#
# Ce script :
#   1. cherche les skills installés dans .claude/skills/ (projet) et ~/.claude/skills/
#   2. ajoute dans chaque agent ceux qui le concernent (champ skills:)
#   3. ignore les skills absents ou marqués disable-model-invocation: true
# Relançable sans risque (idempotent). À lancer APRÈS l'installation des skills.
#
# Usage (à la racine du projet) : .claude/scripts/link-pocock-skills.sh
#        Retirer les liens       : .claude/scripts/link-pocock-skills.sh --unlink
# Compatible bash 3.2 (macOS) et Linux.
# ------------------------------------------------------------------
set -euo pipefail

AGENTS_DIR=".claude/agents"
[ -d "$AGENTS_DIR" ] || { echo "❌ $AGENTS_DIR introuvable : lance ce script à la racine de ton projet." >&2; exit 1; }

UNLINK=0
[ "${1:-}" = "--unlink" ] && UNLINK=1

# agent -> skills souhaités (dans l'ordre de priorité)
skills_for() {
  case "$1" in
    architecte)  echo "codebase-design domain-modeling" ;;
    developpeur) echo "tdd diagnosing-bugs" ;;
    testeur)     echo "tdd diagnosing-bugs" ;;
    relecteur)   echo "code-review" ;;
    *)           echo "" ;;
  esac
}

# renvoie 0 si le skill est installé et préchargeable
skill_ok() {
  for base in ".claude/skills" "$HOME/.claude/skills"; do
    f="$base/$1/SKILL.md"
    if [ -f "$f" ]; then
      if grep -qE '^disable-model-invocation:[[:space:]]*true' "$f"; then
        echo "   ⚠️  $1 : marqué disable-model-invocation, non préchargeable (ignoré)" >&2
        return 1
      fi
      return 0
    fi
  done
  return 1
}

# réécrit le frontmatter : retire l'ancien bloc skills:, ajoute le nouveau
set_skills() {
  file="$1"; shift
  list="$*"
  tmp="$(mktemp)"
  awk -v list="$list" '
    BEGIN { n = split(list, s, " "); fm = 0; skip = 0 }
    {
      if ($0 == "---") {
        fm++
        if (fm == 2 && n > 0) {
          print "skills:"
          for (i = 1; i <= n; i++) print "  - " s[i]
        }
        skip = 0; print; next
      }
      if (fm == 1) {
        if ($0 ~ /^skills:/) { skip = 1; next }
        if (skip && $0 ~ /^[[:space:]]+-/) next
        skip = 0
      }
      print
    }' "$file" > "$tmp"
  cat "$tmp" > "$file" && rm -f "$tmp"
}

FOUND_ANY=0
echo "🔗 Liaison des skills Matt Pocock aux agents"
for agent in architecte developpeur testeur relecteur; do
  file="$AGENTS_DIR/$agent.md"
  [ -f "$file" ] || continue
  linked=""
  if [ "$UNLINK" -eq 0 ]; then
    for sk in $(skills_for "$agent"); do
      if skill_ok "$sk"; then linked="$linked $sk"; FOUND_ANY=1; fi
    done
  fi
  set_skills "$file" $linked
  if [ -n "$linked" ]; then
    echo "   ✔ $agent ←$linked"
  else
    echo "   · $agent : aucun skill lié"
  fi
done

if [ "$UNLINK" -eq 0 ] && [ "$FOUND_ANY" -eq 0 ]; then
  echo ""
  echo "⚠️  Aucun skill de Matt Pocock trouvé dans .claude/skills/ ni ~/.claude/skills/."
  if [ -d ".agents/skills" ] || [ -d "$HOME/.agents/skills" ]; then
    echo "   Des skills existent dans un dossier .agents/skills : relance 'npx skills@latest add mattpocock/skills'"
    echo "   et choisis « Claude Code » comme agent cible, pour qu'ils aillent dans .claude/skills/."
  fi
  echo "   Installe-les d'abord (à la racine du projet) :  npx skills@latest add mattpocock/skills"
  echo "   puis relance :                                  .claude/scripts/link-pocock-skills.sh"
fi
echo ""
echo "ℹ️  Relance 'claude' pour que les agents rechargent leur configuration."
