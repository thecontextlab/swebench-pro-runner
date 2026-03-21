#!/usr/bin/env python3
"""
OpenAI Codex CLI wrapper for SWE-bench evaluation.
Uses the @openai/codex npm package CLI tool.
Follows the same pattern as run_claude.py.
"""
import subprocess
import sys
import os

def main():
    # Read instruction from file
    with open("/instruction.txt", "r") as f:
        instruction = f.read().strip()

    # Match Claude's pattern - use MODEL env var (workflow sets OPENAI_MODEL)
    # Default to gpt-5.3-codex for Tier 3 accounts
    model = os.environ.get("OPENAI_MODEL") or os.environ.get("MODEL", "gpt-5.3-codex")
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if not api_key:
        print("[wrapper] ERROR: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # Log API key presence only (never log key content — public repo artifacts are downloadable)
    print(f"[wrapper] API key detected: {'Yes' if api_key else 'No'}")

    # Build completion instruction with explicit implementation requirement
    completion_instruction = """IMPORTANT: You MUST complete the implementation fully. Do NOT stop after analysis.
Do NOT ask "Would you like me to proceed?" - just implement the fix.
After finding the issue, immediately edit files to make changes.
After editing, run the tests to verify.
Keep working until all tests pass or you hit an error.

""" + instruction

    # Build Codex CLI command
    # Codex expects: codex exec [OPTIONS] [PROMPT]
    # Use --json for JSONL output that can be parsed for metrics
    # Use proper sandbox permissions to allow file access
    cmd = [
        "codex",
        "exec",
        completion_instruction,  # Positional argument for the prompt
        "--model", model,
        "--json",  # JSONL output for metrics parsing
        "--skip-git-repo-check",  # Allow running outside git repo
        "--cd", "/testbed",  # Set working directory explicitly
        "--sandbox", "danger-full-access",  # Full file access (we're in Docker container)
        "-c", "sandbox_permissions=[\"disk-full-read-access\", \"disk-full-write-access\"]",  # Explicit permissions
        "-c", "shell_environment_policy.inherit=all",  # Inherit all environment
        "-c", "shell.quote_style=none"  # Try to prevent extra quoting
    ]

    # Set up environment with API key
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = api_key
    env["CODEX_DISABLE_INTERACTIVE"] = "1"  # Disable interactive prompts

    # Debug: Verify env var is set in subprocess environment
    print(f"[wrapper] Environment check: OPENAI_API_KEY is {'set' if 'OPENAI_API_KEY' in env else 'NOT set'}")

    print(f"[wrapper] Instruction length: {len(instruction)} chars")
    print(f"[wrapper] Model: {model}")
    print(f"[wrapper] Permission mode: danger-full-access (full disk read/write)")
    print(f"[wrapper] Working directory: /testbed")
    print(f"[wrapper] Completion instruction: Added (auto-implementation workaround)")

    print("")
    print("=" * 80)
    print("[wrapper] STEP 0: FULL PROMPT DUMP")
    print("=" * 80)
    print("")
    print("--- COMPLETION INSTRUCTION (passed as positional arg) ---")
    print(completion_instruction)
    print("")
    print("--- END COMPLETION INSTRUCTION ---")
    print("")
    print("--- FULL COMMAND ---")
    # Show command structure without the long prompt
    cmd_display = ["codex", "exec", "<prompt>", "--model", model, "--json", "--skip-git-repo-check",
                   "--sandbox", "danger-full-access", "-c", "sandbox_permissions=[...]", "-c", "shell_environment_policy.inherit=all"]
    print(" ".join(cmd_display))
    print("--- END COMMAND ---")
    print("=" * 80)
    print("")

    # Verify CLI is available (fail fast if not)
    check_cmd = ["which", "codex"]
    check_result = subprocess.run(check_cmd, capture_output=True, text=True)
    if check_result.returncode != 0:
        print("[wrapper] WARNING: Codex CLI not found in PATH!")
        print("[wrapper] WARNING: CLI should be installed by setup.sh or Docker image")
        print("[wrapper] Attempting to run anyway in case it's available...")
    else:
        print(f"[wrapper] Codex CLI found at: {check_result.stdout.strip()}")

    # Authenticate with API key before running
    print("[wrapper] Authenticating Codex with API key...")
    login_cmd = ["codex", "login", "--with-api-key"]
    login_result = subprocess.run(
        login_cmd,
        input=api_key,
        text=True,
        capture_output=True,
        env=env
    )

    if login_result.returncode != 0:
        print(f"[wrapper] ERROR: Failed to authenticate with Codex")
        print(f"[wrapper] stdout: {login_result.stdout}")
        print(f"[wrapper] stderr: {login_result.stderr}")
        sys.exit(1)
    else:
        print("[wrapper] Successfully authenticated with Codex")

    print("[wrapper] Starting OpenAI Codex...")
    print("[wrapper] ========================================")
    sys.stdout.flush()  # Ensure wrapper output is flushed before starting Codex

    # Use Popen to properly capture and stream output
    # This ensures JSONL output is both displayed and saved to agent.log
    process = subprocess.Popen(
        cmd,
        cwd="/testbed",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # Line buffered
        universal_newlines=True
    )

    # Stream output line by line
    for line in iter(process.stdout.readline, ''):
        if line:
            print(line, end='', flush=True)

    # Wait for process to complete
    process.wait()

    print("\n[wrapper] ========================================")
    print(f"[wrapper] Codex CLI exited with code: {process.returncode}")

    sys.exit(process.returncode)

if __name__ == "__main__":
    main()