#!/bin/bash
#
# Migrate Docker images from ghcr.io/manojvas/ to ghcr.io/thecontextlab/
#
# Prerequisites:
#   1. Docker daemon running
#   2. Authenticated to GHCR with write:packages scope for thecontextlab org:
#      echo "$GHCR_PAT" | docker login ghcr.io -u <username> --password-stdin
#
# Usage:
#   ./scripts/migrate-images.sh              # migrate all images
#   ./scripts/migrate-images.sh --dry-run    # show what would be done
#   ./scripts/migrate-images.sh --prune      # prune local images after each push
#

set -euo pipefail

SRC_REGISTRY="ghcr.io/manojvas"
DST_REGISTRY="ghcr.io/thecontextlab"

DRY_RUN=false
PRUNE=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --prune)   PRUNE=true ;;
    --help|-h)
      echo "Usage: $0 [--dry-run] [--prune]"
      echo "  --dry-run  Show what would be done without executing"
      echo "  --prune    Remove local copies after pushing each image"
      exit 0
      ;;
  esac
done

# All images referenced in datasets/*/config.yaml
IMAGES=(
  "swebench-pro-vuls:multi-agent"
  "swebench-pro-flipt:cli"
  "swebench-pro-teleport:cli"
  "swebench-pro-navidrome:multi-agent"
  "swebench-pro-element-web:multi-agent"
  "swebench-pro-nodebb:multi-agent"
  "swebench-pro-tutanota:multi-agent"
  "swebench-pro-webclients:node22-cli"
  "swebench-pro-ansible:multi-agent"
  "swebench-pro-ansible-python311:multi-agent"
  "swebench-pro-qutebrowser:multi-agent"
  "swebench-pro-qutebrowser-python311:multi-agent"
  "swebench-pro-openlibrary-python39:fixed"
  "swebench-pro-openlibrary-python311:fixed"
  "swebench-pro-openlibrary-python312:fixed"
)

TOTAL=${#IMAGES[@]}
SUCCESS=0
FAILED=0
SKIPPED=0

echo "=============================================="
echo "Docker Image Migration"
echo "=============================================="
echo "Source:      $SRC_REGISTRY"
echo "Destination: $DST_REGISTRY"
echo "Images:      $TOTAL"
echo "Dry run:     $DRY_RUN"
echo "Prune:       $PRUNE"
echo "=============================================="
echo ""

# Verify Docker is running (skip for dry-run)
if ! $DRY_RUN; then
  if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running"
    exit 1
  fi
fi

for i in "${!IMAGES[@]}"; do
  img="${IMAGES[$i]}"
  n=$((i + 1))
  src="$SRC_REGISTRY/$img"
  dst="$DST_REGISTRY/$img"

  echo "[$n/$TOTAL] $img"

  if $DRY_RUN; then
    echo "  [DRY RUN] docker pull $src"
    echo "  [DRY RUN] docker tag $src $dst"
    echo "  [DRY RUN] docker push $dst"
    if $PRUNE; then
      echo "  [DRY RUN] docker rmi $src $dst"
    fi
    echo ""
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  # Pull
  echo "  Pulling $src ..."
  if ! docker pull "$src" 2>&1; then
    echo "  FAILED: Could not pull $src"
    FAILED=$((FAILED + 1))
    echo ""
    continue
  fi

  # Tag
  docker tag "$src" "$dst"

  # Push
  echo "  Pushing $dst ..."
  if ! docker push "$dst" 2>&1; then
    echo "  FAILED: Could not push $dst"
    FAILED=$((FAILED + 1))
    echo ""
    continue
  fi

  echo "  OK"
  SUCCESS=$((SUCCESS + 1))

  # Prune local copies to save disk
  if $PRUNE; then
    echo "  Pruning local copies..."
    docker rmi "$src" "$dst" 2>/dev/null || true
  fi

  echo ""
done

echo "=============================================="
echo "Migration Summary"
echo "=============================================="
echo "Total:   $TOTAL"
echo "Success: $SUCCESS"
echo "Failed:  $FAILED"
echo "Skipped: $SKIPPED"
echo "=============================================="

if [ $FAILED -gt 0 ]; then
  echo ""
  echo "Some images failed. Re-run the script to retry."
  exit 1
fi

if ! $DRY_RUN && [ $SUCCESS -gt 0 ]; then
  echo ""
  echo "Next steps:"
  echo "  1. Set image visibility to public in GitHub Packages settings:"
  echo "     https://github.com/orgs/thecontextlab/packages"
  echo ""
  echo "  2. Or use the API to make each package public:"
  echo "     for img in ${IMAGES[*]%%:*}; do"
  echo '       gh api --method PATCH \\'
  echo '         /orgs/thecontextlab/packages/container/$img \\'
  echo '         -f visibility=public'
  echo "     done"
  echo ""
  echo "  3. Set GitHub Actions secrets in the new repo:"
  echo "     gh secret set ANTHROPIC_API_KEY --repo thecontextlab/swebench-pro-runner"
  echo "     gh secret set OPENAI_API_KEY    --repo thecontextlab/swebench-pro-runner"
  echo "     gh secret set GEMINI_API_KEY    --repo thecontextlab/swebench-pro-runner"
  echo "     gh secret set MCP_TOKEN         --repo thecontextlab/swebench-pro-runner"
  echo ""
  echo "  4. Run a smoke test:"
  echo "     gh workflow run swebench-eval.yml -R thecontextlab/swebench-pro-runner \\"
  echo "       -f repo=vuls \\"
  echo '       -f task="future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c" \\'
  echo "       -f model=claude-sonnet-4-5-20250929 \\"
  echo "       -f enable_mcp=false"
fi
