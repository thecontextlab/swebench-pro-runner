#!/usr/bin/env python3
"""Stage 2 of the Bito 3-stage pipeline — plan to agent spec.

Runs Claude Code with `/bito-plan-to-agent-spec`, consuming Stage 1's
`pipeline_artifacts/implementation-plan.md` and producing workstream agent
specs + an execution manifest.

Env vars consumed (see run_claude_stage1.py for full list).
"""
import json
import os
import subprocess
import sys

STAGE_PROMPT = """You are running Stage 2 of a 3-stage Bito pipeline for solving a SWE-Bench Pro task. Stage 1 (a different Claude Code instance) already produced a technical implementation plan. Your job is to transform that plan into workstream agent specs using the `/bito-plan-to-agent-spec` skill.

### Context
This is an automated benchmark run. You are Stage 2. Your input is the plan from Stage 1 on disk. Your outputs — the agent spec files and execution manifest — will be consumed by Stage 3 (running `/bito-agent-spec-executor`) in a separate instance.

### What you must do

1. Read the plan from `pipeline_artifacts/implementation-plan.md`.

2. Invoke `/bito-plan-to-agent-spec` on that plan.
   - Use the BitoAIArchitect MCP server heavily to enrich specs with codebase context — directory structure, pattern exemplars, build/test commands, coding standards, ripple risks.
   - **Auto-approve all checkpoints.** The skill has two checkpoints (workstream graph confirmation, spec review). At each one, auto-approve — confirm with "approved" / "looks good" / "continue". Do not stall waiting for user input.

3. The skill will produce:
   - One agent spec file per workstream, named per its convention: `{ticket-id}-ws{N}-{slug}.agent-spec.md`
   - An execution manifest: `{ticket-id}-execution-manifest.md`

   Since this is a SWE-Bench task with no ticket ID, use `swebench` as the ticket-id prefix (e.g., `swebench-ws1-data-model.agent-spec.md`, `swebench-execution-manifest.md`).

   Save all output files into `pipeline_artifacts/`.

### Hard rules
- **No user prompts.** Do not ask the user anything. Run fully autonomously.
- **Do NOT modify any test file.**
- **Do NOT modify any source code.** Your job is spec production only.
- **Do NOT consult any gold patch.** Work only from the plan.
- At every skill checkpoint, auto-approve and continue immediately.

When all agent spec files and the execution manifest are saved to `pipeline_artifacts/`, stop. Do not proceed to the next stage."""


ALLOWED_TOOLS = "Bash,Edit,Read,Write,Grep,Glob,Task,TodoWrite,mcp__mcp-server"


def build_mcp_config(url: str, token: str) -> str:
    cfg = {"mcpServers": {"mcp-server": {"type": "http", "url": url}}}
    if token:
        cfg["mcpServers"]["mcp-server"]["headers"] = {"Authorization": f"Bearer {token}"}
    return json.dumps(cfg)


def main() -> int:
    plan_path = "/testbed/pipeline_artifacts/implementation-plan.md"
    if not os.path.isfile(plan_path) or os.path.getsize(plan_path) == 0:
        print(f"[stage2] ERROR: Stage 1 output missing or empty: {plan_path}", file=sys.stderr)
        return 2

    model = os.environ.get("MODEL", "claude-opus-4-7")
    effort = os.environ.get("EFFORT", "max")
    mcp_url = os.environ.get("MCP_URL", "")
    mcp_token = os.environ.get("MCP_TOKEN", "")

    if not mcp_url:
        print("[stage2] ERROR: MCP_URL is required (BitoAIArchitect)", file=sys.stderr)
        return 2

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

    print(f"[stage2] model={model} effort={effort} mcp=on task={os.environ.get('TASK_ID', '?')}")
    print(f"[stage2] plan size: {os.path.getsize(plan_path)} bytes")
    print(f"[stage2] launching claude…")
    result = subprocess.run(cmd, cwd="/testbed", env=env)
    print(f"[stage2] claude exit: {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
