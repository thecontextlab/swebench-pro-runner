#!/usr/bin/env python3
"""Stage 1 of the Bito 3-stage pipeline — scope to plan.

Runs a single Claude Code invocation that uses `/bito-scope-to-plan` to
produce `pipeline_artifacts/implementation-plan.md` inside the repo working
directory (/testbed).

Env vars consumed:
  MODEL           Claude model (e.g. claude-opus-4-7)
  EFFORT          Effort level for --effort (default: xhigh)
  MCP_URL         BitoAIArchitect MCP endpoint (required)
  MCP_TOKEN       Bearer token for MCP (required)
  ANTHROPIC_API_KEY  Anthropic API key
  TASK_ID         Task identifier (for logging only)

The prompt text mirrors Stage 1 in `bito_pipeline_three_stage_prompts.md`.
Keep in sync if that file changes.
"""
import json
import os
import subprocess
import sys

STAGE_PROMPT = """You are running Stage 1 of a 3-stage Bito pipeline for solving a SWE-Bench Pro task. Your job is to produce a technical implementation plan using the `/bito-scope-to-plan` skill.

### Context
This is an automated benchmark run. Three separate Claude Code instances handle the three stages. You are Stage 1. Your output — the implementation plan document — will be consumed by Stage 2 (running `/bito-plan-to-agent-spec`) in a separate instance. Save your final plan to `pipeline_artifacts/` in the repo working directory so the next stage can find it.

### What you must do

1. Create `pipeline_artifacts/` in the current repo working directory if it doesn't exist.

2. Invoke `/bito-scope-to-plan` with the problem statement below as the **approved** unit of work.
   - The problem statement IS the approved scope. Treat it as pre-approved — skip any scope-clarification step.
   - Use the BitoAIArchitect MCP server heavily during planning to understand codebase structure, dependencies, and relevant code paths.
   - **Auto-approve all checkpoints.** The skill has three checkpoints (context summary confirmation, approach selection, plan review). At each one, auto-approve — select the most appropriate approach and confirm with "approved" / "continue". Do not stall waiting for user input.

3. The skill will produce a final plan document per its output template (references/output-templates.md). Save that plan to `pipeline_artifacts/implementation-plan.md`.

### Hard rules
- **No user prompts.** Do not ask the user anything. Run fully autonomously.
- **Do NOT modify any test file.**
- **Do NOT consult any gold patch.** Work only from the problem statement.
- Focus on the minimal change needed to fix the issue described.
- At every skill checkpoint, auto-approve and continue immediately.

### Problem statement
<PROBLEM_STATEMENT>
{PROBLEM_STATEMENT}
</PROBLEM_STATEMENT>

When the plan is saved to `pipeline_artifacts/implementation-plan.md`, stop. Do not proceed to the next stage."""


ALLOWED_TOOLS = "Bash,Edit,Read,Write,Grep,Glob,Task,TodoWrite,mcp__mcp-server"


def build_mcp_config(url: str, token: str) -> str:
    cfg = {
        "mcpServers": {
            "mcp-server": {
                "type": "http",
                "url": url,
            }
        }
    }
    if token:
        cfg["mcpServers"]["mcp-server"]["headers"] = {"Authorization": f"Bearer {token}"}
    return json.dumps(cfg)


def main() -> int:
    with open("/instruction.txt") as f:
        problem = f.read().strip()

    model = os.environ.get("MODEL", "claude-opus-4-7")
    effort = os.environ.get("EFFORT", "high")
    mcp_url = os.environ.get("MCP_URL", "")
    mcp_token = os.environ.get("MCP_TOKEN", "")

    if not mcp_url:
        print("[stage1] ERROR: MCP_URL is required (BitoAIArchitect)", file=sys.stderr)
        return 2

    prompt = STAGE_PROMPT.replace("{PROBLEM_STATEMENT}", problem)

    # Audit capture: dump the resolved prompt so reviewers can verify exactly
    # what Claude received — including the BitoAIArchitect instructions and
    # the substituted problem statement.
    os.makedirs("/results/audit", exist_ok=True)
    with open("/results/audit/stage1_prompt.md", "w") as f:
        f.write(prompt)
    if "BitoAIArchitect" not in prompt:
        print("[stage1] ERROR: resolved prompt missing BitoAIArchitect mention", file=sys.stderr)
        return 4
    print(f"[stage1] resolved prompt written to /results/audit/stage1_prompt.md "
          f"({len(prompt)} chars; contains BitoAIArchitect: yes)")

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

    print(f"[stage1] model={model} effort={effort} mcp=on task={os.environ.get('TASK_ID', '?')}")
    print(f"[stage1] problem statement: {len(problem)} chars")
    print(f"[stage1] launching claude…")
    result = subprocess.run(cmd, cwd="/testbed", env=env)
    print(f"[stage1] claude exit: {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
