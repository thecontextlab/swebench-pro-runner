#!/bin/bash
# Fire all 115 SWE-bench Pro tasks through the Bito 3-stage pipeline on
# claude-opus-4-6 effort=high. GitHub Actions concurrency cap (40 runners
# on Pro) does the queueing; we just dispatch them all back-to-back.
#
# Usage:
#   bash scripts/fire_115_opus46.sh                 # dispatch all 115
#   DRY_RUN=1 bash scripts/fire_115_opus46.sh       # print what would dispatch
#   LIMIT=10 bash scripts/fire_115_opus46.sh        # only the first N (smoke test)
#
# Cost estimate (post-hide opus-4-6): ~$0.50-$1.50 per task → $60-$170 total.

set -euo pipefail

LIST="${LIST:-bito_115.txt}"
MODEL="${MODEL:-claude-opus-4-6}"
EFFORT="${EFFORT:-high}"
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
    printf "[%3d] would dispatch: repo=%s model=%s effort=%s task=%s\n" \
      "$count" "$repo" "$MODEL" "$EFFORT" "$task"
  else
    URL=$(gh workflow run swebench-eval-bito.yml \
      -f repo="$repo" \
      -f task="$task" \
      -f model="$MODEL" \
      -f effort="$EFFORT" 2>&1)
    printf "[%3d] %-12s %s\n" "$count" "$repo" "$URL"
    dispatched=$((dispatched + 1))
    sleep 1
  fi
done < "$LIST"

echo
echo "Dispatched: $dispatched"
