#!/bin/bash
# Fire tasks against the standard (vanilla) SWE-bench eval workflow:
# claude-opus-4-6, MCP off, no Bito 3-stage, no skills, no plan mode.
# Effort defaults to whatever the Claude CLI uses by default (run_claude.py
# does not pass --effort).
#
# Usage:
#   bash scripts/fire_phase5_vanilla.sh                # fire all in $LIST
#   LIMIT=3 bash scripts/fire_phase5_vanilla.sh        # smoke
#   DRY_RUN=1 bash scripts/fire_phase5_vanilla.sh
#   LIST=other.txt bash scripts/fire_phase5_vanilla.sh

set -euo pipefail

LIST="${LIST:-bito_phase5_vanilla153.txt}"
MODEL="${MODEL:-claude-opus-4-6}"
LIMIT="${LIMIT:-0}"
DRY_RUN="${DRY_RUN:-0}"

if [ ! -f "$LIST" ]; then
  echo "ERROR: task list $LIST not found"
  exit 1
fi

count=0
dispatched=0
while IFS=$'\t' read -r repo task; do
  count=$((count + 1))
  if [ "$LIMIT" -gt 0 ] && [ "$dispatched" -ge "$LIMIT" ]; then break; fi

  if [ "$DRY_RUN" = "1" ]; then
    printf "[%3d] would dispatch: repo=%s model=%s mcp=false task=%s\n" \
      "$count" "$repo" "$MODEL" "$task"
  else
    URL=$(gh workflow run swebench-eval.yml \
      -f repo="$repo" \
      -f task="$task" \
      -f agent=claude \
      -f model="$MODEL" \
      -f enable_mcp=false 2>&1)
    printf "[%3d] %-12s %s\n" "$count" "$repo" "$URL"
    dispatched=$((dispatched + 1))
    sleep 1
  fi
done < "$LIST"

echo
echo "Dispatched: $dispatched"
