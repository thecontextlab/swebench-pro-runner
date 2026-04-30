#!/bin/bash
# Run a vanilla Claude Code agent against a pre-built per-task ground-truth
# image (built by build_instance_image.sh). Captures pre-verify F2P, runs the
# agent, captures post-verify F2P + P2P, writes result.json.
#
# Pipeline inside the container:
#   1. Install latest Claude Code CLI (overlay over whatever the image baked)
#   2. Symlink /testbed → /app so the existing run_claude.py wrapper works
#      against the upstream-canonical workdir without needing any code change
#   3. Pre-verify: run /run_script.sh <fail_to_pass> → expected to fail
#   4. Pre-verify P2P: run /run_script.sh <pass_to_pass> → expected to pass
#   5. Run the agent
#   6. Capture changes.patch via `git -C /app diff`
#   7. Post-verify F2P
#   8. Post-verify P2P
#   9. Write result.json
#
# Usage:
#   ANTHROPIC_API_KEY=sk-... ./run_on_instance_image.sh <task_id>
#
# Output: /Users/manoj/sources/bitoexperiment/phase-5-150/ground_truth_pilot_results/<task_id>/

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/Users/manoj/sources/swebench-pro-runner}"
SWE_BENCH_PRO_OS_DIR="${SWE_BENCH_PRO_OS_DIR:-/Users/manoj/sources/SWE-bench_Pro-os}"
RESULTS_ROOT="${RESULTS_ROOT:-/Users/manoj/sources/bitoexperiment/phase-5-150/ground_truth_pilot_results}"
PLATFORM="${PLATFORM:-linux/amd64}"
MODEL="${MODEL:-claude-opus-4-6}"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <task_id>" >&2
  exit 1
fi

TASK_ID="$1"

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ERROR: ANTHROPIC_API_KEY env var must be set" >&2
  exit 1
fi

SHORT="$(echo "$TASK_ID" | grep -oE '[a-f0-9]{40}' | head -1 | cut -c1-8)"
INSTANCE_TAG="gt-instance-${SHORT}:latest"

# Verify image exists locally
if ! docker image inspect "$INSTANCE_TAG" >/dev/null 2>&1; then
  echo "ERROR: image $INSTANCE_TAG not found locally. Run build_instance_image.sh first." >&2
  exit 2
fi

# Locate run_script.sh + instance_info.txt
RUN_SCRIPT="$SWE_BENCH_PRO_OS_DIR/run_scripts/instance_$TASK_ID/run_script.sh"
INSTANCE_INFO="$SWE_BENCH_PRO_OS_DIR/run_scripts/instance_$TASK_ID/instance_info.txt"
if [ ! -f "$RUN_SCRIPT" ] || [ ! -f "$INSTANCE_INFO" ]; then
  echo "ERROR: run_script.sh or instance_info.txt missing for $TASK_ID" >&2
  exit 3
fi

# Determine repo (NodeBB / ansible / openlibrary / etc.) for run_claude.py path
# task_id format: <org>__<repo>-<sha>...
REPO="$(echo "$TASK_ID" | sed -E 's/^[^_]+__([^-]+)-.*/\1/')"
case "$REPO" in
  openlibrary)  REPO_DIR=openlibrary ;;
  ansible)      REPO_DIR=ansible ;;
  qutebrowser)  REPO_DIR=qutebrowser ;;
  webclients)   REPO_DIR=webclients ;;
  flipt)        REPO_DIR=flipt ;;
  vuls)         REPO_DIR=vuls ;;
  teleport)     REPO_DIR=teleport ;;
  navidrome)    REPO_DIR=navidrome ;;
  NodeBB)       REPO_DIR=NodeBB ;;
  element-web)  REPO_DIR=element-web ;;
  tutanota)     REPO_DIR=tutanota ;;
  *) echo "ERROR: unknown repo $REPO" >&2; exit 4 ;;
esac
RUN_CLAUDE="$REPO_ROOT/datasets/$REPO_DIR/run_claude.py"
BASE_AGENT_ADAPTER="$REPO_ROOT/datasets/common/base_agent_adapter.py"
if [ ! -f "$RUN_CLAUDE" ]; then
  echo "ERROR: run_claude.py not found for $REPO at $RUN_CLAUDE" >&2
  exit 5
fi

# Parse F2P / P2P / instruction from instance_info.txt
# Format is plain key:value lines; FAIL_TO_PASS / PASS_TO_PASS are JSON arrays
F2P_TESTS="$(python3 -c "
import re, json, sys
text = open('$INSTANCE_INFO').read()
m = re.search(r'^FAIL_TO_PASS:\s*(\[.*?\])', text, re.M | re.S)
arr = json.loads(m.group(1)) if m else []
print('\n'.join(arr))
")"
P2P_TESTS="$(python3 -c "
import re, json
text = open('$INSTANCE_INFO').read()
m = re.search(r'^PASS_TO_PASS:\s*(\[.*?\])', text, re.M | re.S)
arr = json.loads(m.group(1)) if m else []
print('\n'.join(arr))
")"
INSTRUCTION="$(python3 -c "
import re
text = open('$INSTANCE_INFO').read()
# Instruction can span multiple lines; we read everything between 'Instruction:' and the next field
m = re.search(r'^Instruction:\s*(.*?)(?=^[A-Z][A-Z_]+:|\Z)', text, re.M | re.S)
print(m.group(1).strip() if m else '')
")"
if [ -z "$F2P_TESTS" ]; then
  echo "ERROR: could not parse FAIL_TO_PASS from $INSTANCE_INFO" >&2
  exit 6
fi

OUT_DIR="$RESULTS_ROOT/$TASK_ID"
mkdir -p "$OUT_DIR"
echo "$F2P_TESTS" > "$OUT_DIR/fail_to_pass.txt"
echo "$P2P_TESTS" > "$OUT_DIR/pass_to_pass.txt"
echo "$INSTRUCTION" > "$OUT_DIR/instruction.txt"

echo "============================================================"
echo "  task_id:        $TASK_ID"
echo "  repo:           $REPO ($REPO_DIR)"
echo "  image:          $INSTANCE_TAG"
echo "  model:          $MODEL"
echo "  F2P tests:      $(echo "$F2P_TESTS" | wc -l | tr -d ' ')"
echo "  P2P tests:      $(echo "$P2P_TESTS" | wc -l | tr -d ' ')"
echo "  out dir:        $OUT_DIR"
echo "============================================================"

# Run the pipeline. We mount:
#   - run_script.sh from upstream → /run_script.sh
#   - run_claude.py from our datasets → /run_agent.py
#   - base_agent_adapter.py → /base_agent_adapter.py
#   - F2P / P2P / instruction txt files → /
#   - results dir → /results
docker run --rm --platform "$PLATFORM" \
  --entrypoint /bin/bash \
  -v "$OUT_DIR:/results" \
  -v "$RUN_SCRIPT:/run_script.sh:ro" \
  -v "$RUN_CLAUDE:/run_agent.py:ro" \
  -v "$BASE_AGENT_ADAPTER:/base_agent_adapter.py:ro" \
  -v "$OUT_DIR/fail_to_pass.txt:/fail_to_pass.txt:ro" \
  -v "$OUT_DIR/pass_to_pass.txt:/pass_to_pass.txt:ro" \
  -v "$OUT_DIR/instruction.txt:/instruction.txt:ro" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -e MODEL="$MODEL" \
  -e TASK_ID="$TASK_ID" \
  -e MCP_CONFIG="" \
  -e CLAUDE_CODE_DISABLE_NONINTERACTIVE_HINT=1 \
  "$INSTANCE_TAG" \
  -c '
    set -e

    echo "=== Step 1: Install latest Claude Code CLI ==="
    rm -f /usr/local/bin/claude /usr/bin/claude 2>/dev/null || true
    hash -r
    npm install -g @anthropic-ai/claude-code@latest >/tmp/npm.log 2>&1 || {
      echo "npm install failed; tail of log:"; tail -30 /tmp/npm.log; exit 3;
    }
    hash -r
    echo "claude version: $(claude --version 2>&1)"
    echo "claude path: $(command -v claude)"

    echo ""
    echo "=== Step 2: Symlink /testbed -> /app (run_claude.py expects /testbed) ==="
    if [ -d /testbed ]; then
      echo "  /testbed already exists in image; agent runner will use it as-is"
    else
      ln -s /app /testbed
      echo "  symlinked /testbed -> /app"
    fi

    echo ""
    echo "=== Step 3: Pre-verify F2P (should FAIL) ==="
    chmod +x /run_script.sh
    mapfile -t F2P_TESTS < /fail_to_pass.txt
    set +e
    /run_script.sh "${F2P_TESTS[@]}" > /results/pre_verification.log 2>&1
    PRE_F2P_EXIT=$?
    set -e
    echo "  pre-F2P exit: $PRE_F2P_EXIT (expected non-zero)"

    echo ""
    echo "=== Step 4: Pre-verify P2P (should PASS) ==="
    mapfile -t P2P_TESTS < /pass_to_pass.txt
    if [ "${#P2P_TESTS[@]}" -gt 0 ]; then
      set +e
      /run_script.sh "${P2P_TESTS[@]}" > /results/p2p_pre_verification.log 2>&1
      PRE_P2P_EXIT=$?
      set -e
      echo "  pre-P2P exit: $PRE_P2P_EXIT"
    else
      echo "  no P2P tests for this task"
      PRE_P2P_EXIT=0
    fi

    echo ""
    echo "=== Step 5: Run agent (vanilla Claude Code, no MCP) ==="
    cp /base_agent_adapter.py /testbed/base_agent_adapter.py 2>/dev/null || true
    set +e
    python3 /run_agent.py 2>&1 | tee /results/agent.log
    AGENT_EXIT=${PIPESTATUS[0]}
    set -e
    echo "  agent exit: $AGENT_EXIT"

    echo ""
    echo "=== Step 6: Capture changes.patch ==="
    cd /app
    git diff > /results/changes.patch || true
    echo "  patch lines: $(wc -l < /results/changes.patch)"

    echo ""
    echo "=== Step 7: Post-verify F2P ==="
    set +e
    /run_script.sh "${F2P_TESTS[@]}" > /results/verification.log 2>&1
    POST_F2P_EXIT=$?
    set -e
    echo "  post-F2P exit: $POST_F2P_EXIT (0 = resolved)"

    echo ""
    echo "=== Step 8: Post-verify P2P ==="
    if [ "${#P2P_TESTS[@]}" -gt 0 ]; then
      set +e
      /run_script.sh "${P2P_TESTS[@]}" > /results/p2p_verification.log 2>&1
      POST_P2P_EXIT=$?
      set -e
      echo "  post-P2P exit: $POST_P2P_EXIT (0 = no regression)"
    else
      POST_P2P_EXIT=0
    fi

    echo ""
    echo "=== Step 9: Write result.json ==="
    python3 - <<EOF > /results/result.json
import json, os
print(json.dumps({
  "task": "$TASK_ID",
  "model": "$MODEL",
  "mcp_enabled": False,
  "ground_truth_pilot": True,
  "agent_exit_code": $AGENT_EXIT,
  "pre_verify_f2p_exit": $PRE_F2P_EXIT,
  "pre_verify_p2p_exit": $PRE_P2P_EXIT,
  "verification_exit_code": $POST_F2P_EXIT,
  "p2p_verification_exit_code": $POST_P2P_EXIT,
  "f2p_resolved": $POST_F2P_EXIT == 0,
  "p2p_no_regression": $POST_P2P_EXIT == 0,
  "resolved": $POST_F2P_EXIT == 0 and $POST_P2P_EXIT == 0,
}, indent=2))
EOF
    cat /results/result.json
  '

echo
echo "============================================================"
echo "  ✓ Run complete"
echo "  Results: $OUT_DIR"
echo "  Verdict: $(python3 -c "import json; r=json.load(open('$OUT_DIR/result.json')); print('RESOLVED ✓' if r['resolved'] else 'NOT RESOLVED')")"
echo "============================================================"
