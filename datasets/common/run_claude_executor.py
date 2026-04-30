#!/usr/bin/env python3
"""Stage-1-only variant executor — Claude reads the Stage 1 plan + problem
statement and executes directly. No Stage 2 (plan-to-agent-spec) and no
Stage 3 (bito-agent-spec-executor skill). Tests Anand's hypothesis that the
3-stage scaffold over-engineers tasks the executor could solve more flexibly
on its own.

Inputs:
  /testbed/pipeline_artifacts/implementation-plan.md  (from Stage 1)
  /instruction.txt                                    (problem statement)

Env vars consumed (mirrors run_claude_stage{1,3}.py):
  MODEL, EFFORT, MCP_URL, MCP_TOKEN, ANTHROPIC_API_KEY, TASK_ID
"""
import json
import os
import subprocess
import sys

EXECUTOR_PROMPT = """You are executing a fix for the SWE-Bench Pro task described below. A planning stage already produced an implementation plan; your job is to execute it.

<PROBLEM_STATEMENT>
{PROBLEM_STATEMENT}
</PROBLEM_STATEMENT>

<IMPLEMENTATION_PLAN>
{IMPLEMENTATION_PLAN}
</IMPLEMENTATION_PLAN>

### What you must do

1. Read the implementation plan (above and at `pipeline_artifacts/implementation-plan.md`) for the high-level approach.
2. Make the actual code changes in the repo. The plan is a guide; you have full discretion to deviate from it where the codebase reveals a better fit (e.g. an existing pattern the plan didn't anticipate, a different file location, a more idiomatic implementation).
3. Use the BitoAIArchitect MCP server to look up patterns, callers, and ripple risk before non-trivial changes.

### Hard rules
- **No user prompts.** Run fully autonomously.
- **Do NOT modify any test file.**
- **Do NOT read any test file.** Test files have been intentionally withheld (`*_test.go`, `test_*.py`, `*.test.{ts,tsx,js,jsx}`, `*-test.{ts,tsx,js,jsx}`, `*.spec.*`, `*-spec.*`, `tests/`, `test/`, `__tests__/`, `__snapshots__/`, `fixtures/`, `testdata/`, `conftest.py`). If a `Read` or `Bash cat` on a test path errors with "no such file," that is expected — do not work around it.
- **Do NOT run the test suite.** Do not invoke `go test`, `pytest`, `jest`, `npm test`, etc. The pipeline runs all verification after you exit. Tests will literally fail-to-load while you run because the test files are absent.
- **Do NOT consult any gold patch.** Work only from the plan and problem statement.
- Make the **minimal change** needed to fix the issue. Do not refactor unrelated code.
- **Consult BitoAIArchitect before non-trivial changes to existing validation or interface logic.** Especially when the problem statement does not include explicit expected outputs. Use `mcp__BitoAIArchitect__searchCode`, `mcp__BitoAIArchitect__searchSymbols`, `mcp__BitoAIArchitect__getCode`, and `mcp__BitoAIArchitect__queryFieldAcrossRepositories` to understand existing patterns, callers, and invariants before modifying them. At least one MCP call per non-trivial change is expected.
- **Preserve existing validation invariants.** If the existing code raises or rejects on some condition, do NOT relax that condition unless the problem statement explicitly asks for it. Expanding what is accepted is a common way to break pass-to-pass tests.

When all code changes are made, stop. Do not run tests. Do not ask what to do next."""


# Full vanilla tool set + BitoAIArchitect MCP (matches the standing decision
# discussed with Anand: more flexibility than Stage 3's restricted toolset).
ALLOWED_TOOLS = "Bash,Edit,Read,Write,Grep,Glob,WebFetch,Task,TodoWrite,mcp__BitoAIArchitect"


def build_mcp_config(url: str, token: str) -> str:
    cfg = {"mcpServers": {"BitoAIArchitect": {"type": "http", "url": url}}}
    if token:
        cfg["mcpServers"]["BitoAIArchitect"]["headers"] = {"Authorization": f"Bearer {token}"}
    return json.dumps(cfg)


def main() -> int:
    plan_path = "/testbed/pipeline_artifacts/implementation-plan.md"
    if not os.path.isfile(plan_path) or os.path.getsize(plan_path) == 0:
        print(f"[executor] ERROR: Stage 1 output missing or empty: {plan_path}", file=sys.stderr)
        return 2

    with open(plan_path) as f:
        plan = f.read().strip()

    with open("/instruction.txt") as f:
        problem = f.read().strip()

    model = os.environ.get("MODEL", "claude-opus-4-7")
    effort = os.environ.get("EFFORT", "high")
    mcp_url = os.environ.get("MCP_URL", "")
    mcp_token = os.environ.get("MCP_TOKEN", "")

    if not mcp_url:
        print("[executor] ERROR: MCP_URL is required (BitoAIArchitect)", file=sys.stderr)
        return 2

    prompt = EXECUTOR_PROMPT \
        .replace("{PROBLEM_STATEMENT}", problem) \
        .replace("{IMPLEMENTATION_PLAN}", plan)

    os.makedirs("/results/audit", exist_ok=True)
    with open("/results/audit/executor_prompt.md", "w") as f:
        f.write(prompt)

    print(f"[executor] model={model} effort={effort} mcp=on task={os.environ.get('TASK_ID', '?')}")
    print(f"[executor] problem statement: {len(problem)} chars")
    print(f"[executor] implementation plan: {len(plan)} chars")
    print(f"[executor] resolved prompt written to /results/audit/executor_prompt.md ({len(prompt)} chars)")

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

    print(f"[executor] launching claude…")
    result = subprocess.run(cmd, cwd="/testbed", env=env)
    print(f"[executor] claude exit: {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
