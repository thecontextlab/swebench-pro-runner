#!/usr/bin/env python3
"""Stage 3 of the Bito 3-stage pipeline — agent spec executor.

Single Claude Code invocation that walks the execution manifest from Stage 2
and runs `/bito-agent-spec-executor` once per workstream, sequentially,
sharing the same repo state. This is the stage that actually modifies code.

Env vars consumed (see run_claude_stage1.py for full list).
"""
import glob
import json
import os
import subprocess
import sys

STAGE_PROMPT = """You are running Stage 3 of a 3-stage Bito pipeline for solving a SWE-Bench Pro task. Stages 1 and 2 (different Claude Code instances) already produced an implementation plan and workstream agent specs. Your job is to execute each agent spec using the `/bito-agent-spec-executor` skill, making actual code changes in the repo.

### Context
This is an automated benchmark run. You are Stage 3 — the executor. The skill requires TWO inputs per invocation: (1) the original implementation plan and (2) one workstream agent-spec file. Both are in `pipeline_artifacts/`.

### What you must do

1. Read `pipeline_artifacts/swebench-execution-manifest.md` to get the list of workstream spec files, their execution wave order, and the total workstream count.

2. Read the implementation plan from `pipeline_artifacts/implementation-plan.md` — this provides architectural context needed by the executor.

3. For each agent spec file listed in the manifest, in wave order (sequential within waves for this benchmark):
   a. Invoke `/bito-agent-spec-executor` with both the implementation plan and the current workstream spec file as inputs.
   b. The executor **must make the actual code changes** in the repo — it must not stop at planning.
   c. Use the BitoAIArchitect MCP server heavily during execution to look up patterns, callers, and ripple risk before making changes.
   d. If the skill hits any checkpoint or confirmation prompt, auto-approve with "approved" / "continue" / "yes" and keep going.
   e. The executor will run its own verification gates and two-stage review (spec compliance + code quality) per the skill definition. Let it complete fully.

4. If the manifest lists N workstreams, invoke the executor N times, once per spec, sequentially.

### Hard rules
- **No user prompts.** Do not ask the user anything. Run fully autonomously.
- **Do NOT modify any test file.**
- **Do NOT consult any gold patch.** Work only from the workstream specs and implementation plan.
- Make the **minimal change** needed to fix the issue. Do not refactor unrelated code.
- At every skill checkpoint or confirmation prompt, auto-approve and continue.
- After all workstreams are executed, note the total workstream count (e.g., "workstreams=3") for downstream recording.
- **Skip branch creation.** The executor skill normally creates a git branch per workstream. For this benchmark, skip branching — make changes directly on the current working tree. All workstreams apply to the same repo state sequentially.

When all workstream specs have been executed and code changes are in the repo, stop. Do not run tests. Do not ask what to do next."""


ALLOWED_TOOLS = "Bash,Edit,Read,Write,Grep,Glob,Task,TodoWrite,mcp__BitoAIArchitect"


def build_mcp_config(url: str, token: str) -> str:
    cfg = {"mcpServers": {"BitoAIArchitect": {"type": "http", "url": url}}}
    if token:
        cfg["mcpServers"]["BitoAIArchitect"]["headers"] = {"Authorization": f"Bearer {token}"}
    return json.dumps(cfg)


def main() -> int:
    artifacts = "/testbed/pipeline_artifacts"
    manifest = os.path.join(artifacts, "swebench-execution-manifest.md")
    plan = os.path.join(artifacts, "implementation-plan.md")

    missing = [p for p in (plan, manifest) if not os.path.isfile(p) or os.path.getsize(p) == 0]
    if missing:
        print(f"[stage3] ERROR: missing or empty stage 2 outputs: {missing}", file=sys.stderr)
        return 2

    specs = sorted(glob.glob(os.path.join(artifacts, "swebench-ws*.agent-spec.md")))
    if not specs:
        print(f"[stage3] ERROR: no workstream spec files under {artifacts}", file=sys.stderr)
        return 2

    model = os.environ.get("MODEL", "claude-opus-4-7")
    effort = os.environ.get("EFFORT", "high")
    mcp_url = os.environ.get("MCP_URL", "")
    mcp_token = os.environ.get("MCP_TOKEN", "")

    if not mcp_url:
        print("[stage3] ERROR: MCP_URL is required (BitoAIArchitect)", file=sys.stderr)
        return 2

    os.makedirs("/results/audit", exist_ok=True)
    with open("/results/audit/stage3_prompt.md", "w") as f:
        f.write(STAGE_PROMPT)
    if "BitoAIArchitect" not in STAGE_PROMPT:
        print("[stage3] ERROR: prompt missing BitoAIArchitect mention", file=sys.stderr)
        return 4
    print(f"[stage3] resolved prompt written to /results/audit/stage3_prompt.md "
          f"({len(STAGE_PROMPT)} chars; contains BitoAIArchitect: yes)")

    cmd = [
        "claude", "--print",
        "--permission-mode", "acceptEdits",
        "--allowedTools", ALLOWED_TOOLS,
        "-p", STAGE_PROMPT,
        "--output-format", "stream-json",
        "--verbose",
        "--model", model,
        "--effort", effort,
        "--mcp-config", build_mcp_config(mcp_url, mcp_token),
    ]

    env = os.environ.copy()
    env["CLAUDE_CODE_DISABLE_NONINTERACTIVE_HINT"] = "1"

    print(f"[stage3] model={model} effort={effort} mcp=on task={os.environ.get('TASK_ID', '?')}")
    print(f"[stage3] manifest: {manifest}")
    print(f"[stage3] workstream specs discovered: {len(specs)}")
    for s in specs:
        print(f"  - {os.path.basename(s)}")
    print(f"[stage3] launching claude…")
    result = subprocess.run(cmd, cwd="/testbed", env=env)
    print(f"[stage3] claude exit: {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
