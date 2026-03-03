#!/usr/bin/env bash
# Build and optionally push SWE-bench Pro Docker images.
#
# Usage:
#   ./docker/build.sh vuls-multi-agent          # Build one image
#   ./docker/build.sh --all                     # Build all images
#   ./docker/build.sh --push vuls-multi-agent   # Build and push
#   ./docker/build.sh --no-cache flipt          # Fresh rebuild
#   ./docker/build.sh --list                    # List available Dockerfiles
#
# The script must be run from the repository root.

set -euo pipefail

REGISTRY="ghcr.io"
REGISTRY_ORG="thecontextlab"
PUSH=false
NO_CACHE=false
BUILD_ALL=false
LIST_ONLY=false
PLATFORM="linux/amd64"
TARGETS=()

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS] [DOCKERFILE_SUFFIX ...]

Build SWE-bench Pro Docker images from docker/Dockerfile.* files.

Arguments:
  DOCKERFILE_SUFFIX   One or more Dockerfile suffixes (e.g., vuls-multi-agent, flipt)

Options:
  --all               Build all Dockerfiles in docker/
  --push              Push images to GHCR after building
  --no-cache          Build without Docker cache
  --platform PLAT     Target platform (default: linux/amd64)
  --list              List available Dockerfiles and exit
  -h, --help          Show this help

Examples:
  $(basename "$0") vuls-multi-agent
  $(basename "$0") --push --no-cache flipt teleport
  $(basename "$0") --all --push
EOF
  exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --push)     PUSH=true; shift ;;
    --no-cache) NO_CACHE=true; shift ;;
    --all)      BUILD_ALL=true; shift ;;
    --list)     LIST_ONLY=true; shift ;;
    --platform) PLATFORM="$2"; shift 2 ;;
    -h|--help)  usage ;;
    -*)         echo "Unknown option: $1" >&2; exit 1 ;;
    *)          TARGETS+=("$1"); shift ;;
  esac
done

# Verify we're in the repo root
if [ ! -d "docker" ]; then
  echo "ERROR: docker/ directory not found. Run this script from the repository root." >&2
  exit 1
fi

# Resolve suffix to full GHCR image name
suffix_to_image() {
  local suffix="$1"
  local name

  # Strip -multi-agent suffix for the image name
  name=$(echo "$suffix" | sed 's/-multi-agent$//')

  # Special case: nodebb -> NodeBB
  if [ "$name" = "nodebb" ]; then
    name="NodeBB"
  fi

  echo "${REGISTRY}/${REGISTRY_ORG}/swebench-pro-${name}:multi-agent"
}

# List mode
if [ "$LIST_ONLY" = true ]; then
  echo "Available Dockerfiles:"
  for f in docker/Dockerfile.*; do
    suffix="${f#docker/Dockerfile.}"
    image=$(suffix_to_image "$suffix")
    echo "  $suffix  ->  $image"
  done
  exit 0
fi

# Build a single image
build_image() {
  local suffix="$1"
  local dockerfile="docker/Dockerfile.${suffix}"
  local image

  if [ ! -f "$dockerfile" ]; then
    echo "ERROR: $dockerfile not found" >&2
    return 1
  fi

  image=$(suffix_to_image "$suffix")

  echo ""
  echo "============================================================"
  echo "Building: $dockerfile"
  echo "Image:    $image"
  echo "Platform: $PLATFORM"
  echo "============================================================"

  local build_args=(
    --file "$dockerfile"
    --tag "$image"
    --platform "$PLATFORM"
  )

  if [ "$NO_CACHE" = true ]; then
    build_args+=(--no-cache)
  fi

  docker build "${build_args[@]}" .

  echo "Build complete: $image"

  if [ "$PUSH" = true ]; then
    echo "Pushing: $image"
    docker push "$image"
    echo "Push complete: $image"
  fi
}

# Collect targets
if [ "$BUILD_ALL" = true ]; then
  for f in docker/Dockerfile.*; do
    suffix="${f#docker/Dockerfile.}"
    TARGETS+=("$suffix")
  done
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
  echo "ERROR: No Dockerfiles specified. Use --all or provide suffixes." >&2
  echo "Run with --list to see available Dockerfiles." >&2
  exit 1
fi

# Summary
echo "============================================================"
echo "SWE-bench Pro Docker Build"
echo "============================================================"
echo "Targets:   ${#TARGETS[@]} image(s)"
echo "Push:      $PUSH"
echo "No cache:  $NO_CACHE"
echo "Platform:  $PLATFORM"
echo "============================================================"

# Build each target
SUCCESS=0
FAILURE=0

for suffix in "${TARGETS[@]}"; do
  if build_image "$suffix"; then
    SUCCESS=$((SUCCESS + 1))
  else
    FAILURE=$((FAILURE + 1))
    echo "FAILED: $suffix" >&2
  fi
done

echo ""
echo "============================================================"
echo "Build Summary"
echo "============================================================"
echo "Total:   ${#TARGETS[@]}"
echo "Success: $SUCCESS"
echo "Failed:  $FAILURE"

if [ "$FAILURE" -gt 0 ]; then
  exit 1
fi
