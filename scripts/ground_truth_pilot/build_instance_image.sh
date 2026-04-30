#!/bin/bash
# Build a SWE-bench Pro per-task image directly from the upstream
# SWE-bench_Pro-os Dockerfiles, with FROM lines rewritten to use public
# Docker Hub instead of the AWS ECR mirror the upstream points at.
#
# Two-stage build:
#   1. base_dockerfile (system deps + repo clone scaffolding) → local tag
#   2. instance_dockerfile (FROM base, runs preprocess.sh + build.sh) → local tag
#
# Usage:
#   ./build_instance_image.sh <task_id>
#   ./build_instance_image.sh <task_id> --push <registry/prefix>  # optional push
#
# task_id examples (full upstream form including v-suffix):
#   internetarchive__openlibrary-03095f2680f7516fca35a58e665bf2a41f006273-v8717e18970bcdc4e0d2cea3b1527752b21e74866
#   protonmail__webclients-01ea5214d11e0df8b7170d91bafd34f23cb0f2b1
#   future-architect__vuls-f6cc8c26a9c08a18e3d1f48dab0bbd3aaaa1e24c-vXXX
#
# Output tags:
#   gt-base-<short>:latest      (built locally; not auto-pushed unless --push)
#   gt-instance-<short>:latest  (built locally on top; same)
# where <short> = first 8 chars of the patch SHA in task_id.

set -euo pipefail

SWE_BENCH_PRO_OS_DIR="${SWE_BENCH_PRO_OS_DIR:-/Users/manoj/sources/SWE-bench_Pro-os}"
PLATFORM="${PLATFORM:-linux/amd64}"  # Apple Silicon: must be amd64 (Qt/Xvfb don't run on arm64)

if [ $# -lt 1 ]; then
  echo "Usage: $0 <task_id> [--push <registry/prefix>]" >&2
  exit 1
fi

TASK_ID="$1"
shift
PUSH_REGISTRY=""
if [ "${1:-}" = "--push" ]; then
  PUSH_REGISTRY="${2:-}"
  if [ -z "$PUSH_REGISTRY" ]; then
    echo "ERROR: --push requires a registry argument (e.g. ghcr.io/thecontextlab/gt)" >&2
    exit 1
  fi
fi

BASE_DIR="$SWE_BENCH_PRO_OS_DIR/dockerfiles/base_dockerfile/instance_$TASK_ID"
INSTANCE_DIR="$SWE_BENCH_PRO_OS_DIR/dockerfiles/instance_dockerfile/instance_$TASK_ID"

if [ ! -d "$BASE_DIR" ]; then
  echo "ERROR: base_dockerfile dir not found: $BASE_DIR" >&2
  exit 2
fi
if [ ! -d "$INSTANCE_DIR" ]; then
  echo "ERROR: instance_dockerfile dir not found: $INSTANCE_DIR" >&2
  exit 2
fi

# Derive a short tag — first 8 chars of the 40-char patch SHA.
# task_id format: <org>__<repo>-<sha40>(-v<vsha>)?
SHORT="$(echo "$TASK_ID" | grep -oE '[a-f0-9]{40}' | head -1 | cut -c1-8)"
if [ -z "$SHORT" ]; then
  echo "ERROR: could not derive 8-char tag from task_id $TASK_ID" >&2
  exit 3
fi

BASE_TAG="gt-base-${SHORT}:latest"
INSTANCE_TAG="gt-instance-${SHORT}:latest"

echo "============================================================"
echo "  task_id:      $TASK_ID"
echo "  short:        $SHORT"
echo "  base_dir:     $BASE_DIR"
echo "  instance_dir: $INSTANCE_DIR"
echo "  base_tag:     $BASE_TAG"
echo "  instance_tag: $INSTANCE_TAG"
echo "  platform:     $PLATFORM"
echo "============================================================"

WORK="$(mktemp -d -t gt_pilot_${SHORT}_XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

# ---------- Stage 1: base ----------
cp -R "$BASE_DIR" "$WORK/base"

# Rewrite FROM lines:
#   084828598639.dkr.ecr.us-west-2.amazonaws.com/docker-hub/library/<image>  →  <image>  (public Docker Hub)
# Sample: python:3.10-slim-bookworm, ubuntu:20.04, etc.
perl -i -pe 's{^FROM\s+084828598639\.dkr\.ecr\.us-west-2\.amazonaws\.com/docker-hub/library/(\S+)}{FROM $1}' "$WORK/base/Dockerfile"

echo
echo "=== Base FROM after rewrite ==="
grep -E "^FROM\s" "$WORK/base/Dockerfile" | head -3
echo

echo "=== Building base image ==="
BUILD_LOG_BASE="$(mktemp -t gt_base_log_XXXXXX)"
if ! docker build --platform "$PLATFORM" -t "$BASE_TAG" "$WORK/base" 2>&1 | tee "$BUILD_LOG_BASE" | tail -20; then
  echo "ERROR: base build failed; last 50 lines of log:" >&2
  tail -50 "$BUILD_LOG_BASE" >&2
  exit 4
fi

# ---------- Stage 2: instance ----------
cp -R "$INSTANCE_DIR" "$WORK/instance"

# Rewrite FROM lines. Three forms observed upstream:
#   1. 084828598639.dkr.ecr.us-west-2.amazonaws.com/sweap-images/<repo>:base_<...>  → local base tag
#   2. base_<repo>___<date>.<sha>                                                   → local base tag (logical, dated)
#   3. base_<repo>                                                                  → local base tag (logical, undated)
# Match any line that looks like a private/logical base reference and replace with our local tag.
perl -i -pe 's{^FROM\s+(084828598639\.dkr\.ecr\.us-west-2\.amazonaws\.com/sweap-images/\S+|base_\S+)}{FROM '"$BASE_TAG"'}' "$WORK/instance/Dockerfile"

echo
echo "=== Instance FROM after rewrite ==="
grep -E "^FROM\s" "$WORK/instance/Dockerfile" | head -3
echo

echo "=== Building instance image (preprocess.sh + build.sh run during build; ~5-15 min) ==="
BUILD_LOG_INSTANCE="$(mktemp -t gt_instance_log_XXXXXX)"
if ! docker build --platform "$PLATFORM" -t "$INSTANCE_TAG" "$WORK/instance" 2>&1 | tee "$BUILD_LOG_INSTANCE" | tail -20; then
  echo "ERROR: instance build failed; last 50 lines of log:" >&2
  tail -50 "$BUILD_LOG_INSTANCE" >&2
  exit 5
fi

# ---------- Optional push ----------
if [ -n "$PUSH_REGISTRY" ]; then
  PUSHED_BASE="$PUSH_REGISTRY/gt-base-${SHORT}:latest"
  PUSHED_INSTANCE="$PUSH_REGISTRY/gt-instance-${SHORT}:latest"
  docker tag "$BASE_TAG" "$PUSHED_BASE"
  docker tag "$INSTANCE_TAG" "$PUSHED_INSTANCE"
  docker push "$PUSHED_BASE"
  docker push "$PUSHED_INSTANCE"
  echo "Pushed: $PUSHED_BASE"
  echo "Pushed: $PUSHED_INSTANCE"
fi

echo
echo "============================================================"
echo "  ✓ Build complete"
echo "  Base:     $BASE_TAG ($(docker images --format '{{.Size}}' "$BASE_TAG"))"
echo "  Instance: $INSTANCE_TAG ($(docker images --format '{{.Size}}' "$INSTANCE_TAG"))"
echo "============================================================"
