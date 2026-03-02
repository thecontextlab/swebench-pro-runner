#!/usr/bin/env python3
"""
Claude Code wrapper script for SWE-bench Pro evaluation.
Avoids shell escaping issues by using subprocess with list args.
"""
import subprocess
import sys
import os
import json

# CLAUDE.md content for MCP tool prompting (when MCP is enabled)
CLAUDE_MD_MCP_PROMPT = """# MCP Server - Usage Instructions

## Rule: Use MCP Tools When Available

**For questions about code, architecture, features, or implementation:**
- Call MCP tools to search and explore the codebase
- Use IN PARALLEL with local file exploration

## Tools

**Code search tools (if available):**
- `searchCode` - Search code by pattern/keyword across repos
- `searchSymbols` - Find functions, classes, methods
- `getCode` - Read specific file contents

## Quick Rules

**Do:**
- Use MCP tools + explore local files in parallel
- Never ask permission - just call tools

**Don't:**
- Never skip MCP tools because you see local files
- Never ask "Would you like me to search?"
"""

def main():
    # Read instruction from file
    with open("/instruction.txt", "r") as f:
        instruction = f.read().strip()

    model = os.environ.get("MODEL", "claude-sonnet-4-5-20250929")
    mcp_config = os.environ.get("MCP_CONFIG", "")
    mcp_url = os.environ.get("MCP_URL", "")
    mcp_token = os.environ.get("MCP_TOKEN", "")

    # Build the completion instruction
    completion_instruction = """IMPORTANT: You MUST complete the implementation fully. Do NOT stop after analysis.
Do NOT ask "Would you like me to proceed?" - just implement the fix.
After finding the issue, immediately use the Edit tool to make changes.
After editing, run the tests with Bash to verify.
Keep working until all tests pass or you hit an error.

""" + instruction

    # If MCP is enabled, append a hint to use MCP tools
    if mcp_config or mcp_url:
        completion_instruction += "\n\nConsult MCP tools when relevant for code search and exploration."

    # Build allowedTools list - include MCP tools if MCP is enabled
    allowed_tools = "Bash,Edit,Read,Write,Grep,Glob,WebFetch,Task,TodoWrite"
    if mcp_config or mcp_url:
        # Add MCP tools to allowed list
        allowed_tools += ",mcp__mcp-server"
        print(f"[wrapper] MCP tools added to allowedTools")

        # Write CLAUDE.md to /testbed with MCP usage instructions
        claude_md_path = "/testbed/CLAUDE.md"
        print(f"[wrapper] Writing CLAUDE.md to {claude_md_path}")
        with open(claude_md_path, "w") as f:
            f.write(CLAUDE_MD_MCP_PROMPT)
        print("[wrapper] CLAUDE.md written successfully")

    cmd = [
        "claude", "--print",
        "--permission-mode", "acceptEdits",
        "--allowedTools", allowed_tools,
        "-p", completion_instruction,
        "--output-format", "stream-json",
        "--verbose",
    ]

    if model:
        cmd.extend(["--model", model])

    # Add MCP config if provided
    if mcp_config or mcp_url:
        if mcp_config:
            mcp_config_str = mcp_config
            print("[wrapper] Using MCP_CONFIG from environment")
        elif mcp_url:
            mcp_config_dict = {
                "mcpServers": {
                    "mcp-server": {
                        "type": "http",
                        "url": mcp_url
                    }
                }
            }

            # Add authentication header if token is provided
            if mcp_token:
                mcp_config_dict["mcpServers"]["mcp-server"]["headers"] = {
                    "Authorization": f"Bearer {mcp_token}"
                }
                print(f"[wrapper] MCP configured WITH bearer token authentication")
            else:
                print(f"[wrapper] MCP configured WITHOUT authentication (no token provided)")

            mcp_config_str = json.dumps(mcp_config_dict)

        cmd.extend(["--mcp-config", mcp_config_str])

    # Set up environment
    env = os.environ.copy()
    env["CLAUDE_CODE_DISABLE_NONINTERACTIVE_HINT"] = "1"

    print(f"[wrapper] Instruction length: {len(instruction)} chars")
    print(f"[wrapper] Model: {model}")
    print(f"[wrapper] MCP enabled: {bool(mcp_config or mcp_url)}")
    print(f"[wrapper] MCP authenticated: {bool(mcp_token)}")
    print(f"[wrapper] Permission mode: acceptEdits")
    if mcp_url:
        print(f"[wrapper] MCP URL: {mcp_url}")

    print("")
    print("=" * 80)
    print("[wrapper] PROMPT DUMP")
    print("=" * 80)
    print("")
    print("--- COMPLETION INSTRUCTION (passed via -p) ---")
    print(completion_instruction)
    print("--- END COMPLETION INSTRUCTION ---")
    print("")
    print("--- FULL COMMAND ---")
    print(" ".join(cmd[:10]) + " ...")
    print("--- END COMMAND ---")
    print("=" * 80)
    print("")

    print("[wrapper] Starting Claude Code...")

    result = subprocess.run(cmd, cwd="/testbed", env=env)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
