#!/usr/bin/env python3
"""Stage 4 — verification-feedback iteration (Approach A from CTA #7).

Fires after a first-pass run when post-verify F2P fails. The first pass already
produced source edits (changes.patch) and a verification.log capturing the
exact pytest/jest/go-test failure output. This stage hands all of that back to
a fresh Claude session so it can produce a corrective second-pass patch.

METHODOLOGICAL CAVEAT (Approach A):
The verification.log contains test assertion text (e.g. "expected X, got Y").
Feeding it back to the agent is functionally equivalent to letting the agent
read the test source. This is intentional per the team's decision; results
from runs using Stage 4 are NOT directly comparable to runs using only test
hiding (vanilla baseline / Stage-1-only variant). They should be compared
against each other or against a vanilla-with-feedback control.

Inputs (all in the container's mounted paths):
  /instruction.txt                                     — problem statement
  /testbed/pipeline_artifacts/implementation-plan.md   — Stage 1 plan output
  /results/changes.patch                               — first-pass edits
  /results/verification.log                            — first-pass post-verify output
  (P2P log if present too: /results/p2p_verification.log)

Env vars consumed:
  MODEL, EFFORT, MCP_URL, MCP_TOKEN, ANTHROPIC_API_KEY, TASK_ID
"""
import json
import os
import subprocess
import sys

STAGE4_PROMPT = """You are running Stage 4 of a Bito pipeline — the verification-feedback iteration. A first pass already produced source edits, but the F2P tests did not pass. Your job is to read the test failure output and produce a corrective patch.

<PROBLEM_STATEMENT>
{PROBLEM_STATEMENT}
</PROBLEM_STATEMENT>

<IMPLEMENTATION_PLAN>
{IMPLEMENTATION_PLAN}
</IMPLEMENTATION_PLAN>

<FIRST_PASS_CHANGES>
{FIRST_PASS_PATCH}
</FIRST_PASS_CHANGES>

<F2P_VERIFICATION_OUTPUT>
{F2P_VERIFY_LOG}
</F2P_VERIFICATION_OUTPUT>

<P2P_VERIFICATION_OUTPUT>
{P2P_VERIFY_LOG}
</P2P_VERIFICATION_OUTPUT>

### What you must do

1. Read the problem statement, plan, first-pass changes, and verification output above.
2. Diagnose why the F2P tests failed (and whether the P2P regressed). The verification output shows test names plus assertion messages or error stack traces.
3. Modify the source code to address the root cause. You may keep, refine, or replace the first-pass edits.
4. Use BitoAIArchitect MCP (`mcp__BitoAIArchitect__searchCode`, `searchSymbols`, `getCode`, `queryFieldAcrossRepositories`) to verify pattern alignment before editing. At least one MCP call per non-trivial change is expected.

### Hard rules
- **No user prompts.** Run autonomously.
- **Do NOT modify any test file.**
- **Do NOT read any test file.** Test files have been intentionally withheld (`*_test.go`, `test_*.py`, `*.test.{ts,tsx,js,jsx}`, `*-test.*`, `*.spec.*`, `*-spec.*`, `tests/`, `test/`, `__tests__/`, `__snapshots__/`, `fixtures/`, `testdata/`, `conftest.py`). The verification output above is your only authorized source of test-failure information.
- **Do NOT run the test suite.** The pipeline runs verification after you exit.
- **Do NOT consult any gold patch.** Work only from the inputs above.
- Make the **minimal change** needed. If the first-pass changes are mostly right, refine them rather than rewriting from scratch.
- **Preserve existing validation invariants.** If the original code rejects on some condition, do NOT relax that condition unless the problem statement explicitly asks for it. Expanding what is accepted is a common P2P-regression cause.

When your corrective edits are complete, stop. Do not run tests. Do not ask what to do next."""


ALLOWED_TOOLS = "Bash,Edit,Read,Write,Grep,Glob,WebFetch,Task,TodoWrite,mcp__BitoAIArchitect"

# Cap the verification log size we feed back to keep prompts in budget. The
# audit reconciler shows test failure summaries are usually < 5KB; cap at 50KB
# to be safe.
MAX_VERIFY_LOG_BYTES = 50_000
MAX_PATCH_BYTES = 100_000


def build_mcp_config(url: str, token: str) -> str:
    cfg = {"mcpServers": {"BitoAIArchitect": {"type": "http", "url": url}}}
    if token:
        cfg["mcpServers"]["BitoAIArchitect"]["headers"] = {"Authorization": f"Bearer {token}"}
    return json.dumps(cfg)


def read_truncated(path: str, max_bytes: int) -> str:
    if not os.path.isfile(path):
        return f"(file not present: {path})"
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes + 1)
        if len(data) > max_bytes:
            return data[:max_bytes].decode("utf-8", errors="replace") + f"\n\n[... TRUNCATED at {max_bytes} bytes ...]"
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        return f"(error reading {path}: {e})"


def main() -> int:
    plan_path = "/testbed/pipeline_artifacts/implementation-plan.md"
    if not os.path.isfile(plan_path) or os.path.getsize(plan_path) == 0:
        print(f"[stage4] ERROR: Stage 1 plan missing or empty: {plan_path}", file=sys.stderr)
        return 2

    patch_path = "/results/changes.patch"
    verify_path = "/results/verification.log"
    p2p_verify_path = "/results/p2p_verification.log"

    if not os.path.isfile(verify_path):
        print(f"[stage4] ERROR: first-pass verification.log missing: {verify_path}", file=sys.stderr)
        return 2

    plan = open(plan_path).read().strip()
    problem = open("/instruction.txt").read().strip()
    patch = read_truncated(patch_path, MAX_PATCH_BYTES)
    f2p_log = read_truncated(verify_path, MAX_VERIFY_LOG_BYTES)
    p2p_log = read_truncated(p2p_verify_path, MAX_VERIFY_LOG_BYTES)

    model = os.environ.get("MODEL", "claude-opus-4-7")
    effort = os.environ.get("EFFORT", "high")
    mcp_url = os.environ.get("MCP_URL", "")
    mcp_token = os.environ.get("MCP_TOKEN", "")

    if not mcp_url:
        print("[stage4] ERROR: MCP_URL is required", file=sys.stderr)
        return 2

    prompt = (STAGE4_PROMPT
              .replace("{PROBLEM_STATEMENT}", problem)
              .replace("{IMPLEMENTATION_PLAN}", plan)
              .replace("{FIRST_PASS_PATCH}", patch)
              .replace("{F2P_VERIFY_LOG}", f2p_log)
              .replace("{P2P_VERIFY_LOG}", p2p_log))

    os.makedirs("/results/audit", exist_ok=True)
    with open("/results/audit/stage4_prompt.md", "w") as f:
        f.write(prompt)

    print(f"[stage4] model={model} effort={effort} mcp=on task={os.environ.get('TASK_ID', '?')}")
    print(f"[stage4] problem statement: {len(problem)} chars")
    print(f"[stage4] implementation plan: {len(plan)} chars")
    print(f"[stage4] first-pass patch: {len(patch)} chars")
    print(f"[stage4] F2P verify log: {len(f2p_log)} chars")
    print(f"[stage4] P2P verify log: {len(p2p_log)} chars")
    print(f"[stage4] resolved prompt: {len(prompt)} chars (saved to /results/audit/stage4_prompt.md)")

    cmd = [
        "claude", "--print",
        "--permission-mode", "acceptEdits",
        "--allowedTools", ALLOWED_TOOLS,
        "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--model", model,
        "--effort", effort,
        "--mcp-config", build_mcp_config(mcp_url, mcp_token),
    ]

    env = os.environ.copy()
    env["CLAUDE_CODE_DISABLE_NONINTERACTIVE_HINT"] = "1"

    print(f"[stage4] launching claude...")
    result = subprocess.run(cmd, cwd="/testbed", env=env)
    print(f"[stage4] claude exit: {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
