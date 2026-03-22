#!/usr/bin/env python3
"""
Cursor Agent CLI wrapper for SWE-bench Pro evaluation.
Uses the Cursor CLI 'cursor-agent' binary in headless print mode.

NOTE: Cursor CLI (beta) may hang after completing in --print mode.
This wrapper implements an idle-timeout watchdog (ADR-016) that sends
SIGTERM if no output for CURSOR_IDLE_TIMEOUT seconds (default: 120).

Cursor uses subscription-based pricing, so cost is reported as $0.00
unless token counts are available in the output (ADR-015).
"""
import subprocess
import sys
import os
import threading
import time


# Idle timeout: kill process if no output for this many seconds
IDLE_TIMEOUT_SECONDS = int(os.environ.get("CURSOR_IDLE_TIMEOUT", "120"))
# Hard timeout: absolute maximum runtime
HARD_TIMEOUT_SECONDS = int(os.environ.get("CURSOR_HARD_TIMEOUT", str(40 * 60)))


def main():
    # Read instruction from file
    with open("/instruction.txt", "r") as f:
        instruction = f.read().strip()

    model = os.environ.get("CURSOR_MODEL") or os.environ.get("MODEL", "")
    api_key = os.environ.get("CURSOR_API_KEY", "")
    mcp_url = os.environ.get("MCP_URL", "")
    mcp_config = os.environ.get("MCP_CONFIG", "")

    if not api_key:
        print("[wrapper] ERROR: CURSOR_API_KEY environment variable not set")
        sys.exit(1)

    # Debug: Log API key presence (not the actual value)
    print(f"[wrapper] API key detected: {'Yes' if api_key else 'No'}")

    # Build completion instruction with explicit implementation requirement
    completion_instruction = """IMPORTANT: You MUST complete the implementation fully. Do NOT stop after analysis.
Do NOT ask "Would you like me to proceed?" - just implement the fix.
After finding the issue, immediately edit files to make changes.
After editing, run the tests to verify.
Keep working until all tests pass or you hit an error.

NOTE: This is a Python project. Use pytest for running tests.

""" + instruction

    # MCP: log warning if enabled (headless MCP has known issues in Cursor CLI beta)
    if mcp_url or mcp_config:
        print("[wrapper] WARNING: Cursor CLI MCP support is experimental in headless mode")
        print("[wrapper] MCP tools may not be available. Proceeding without MCP.")

    # Build Cursor CLI command
    # --print: non-interactive/headless mode
    # --force: autonomous file modifications without confirmation prompts
    # --output-format json: structured output for metrics parsing
    cmd = [
        "cursor-agent",
        "-p",
        "--output-format", "json",
        "--force",
    ]

    if model:
        cmd.extend(["-m", model])

    # Prompt must be the last positional argument
    cmd.append(completion_instruction)

    # Set up environment with API key
    env = os.environ.copy()
    env["CURSOR_API_KEY"] = api_key

    print(f"[wrapper] Instruction length: {len(instruction)} chars")
    print(f"[wrapper] Model: {model or '(cursor default)'}")
    print(f"[wrapper] MCP enabled: {bool(mcp_url or mcp_config)}")
    print(f"[wrapper] Permission mode: force (autonomous file modifications)")
    print(f"[wrapper] Idle timeout: {IDLE_TIMEOUT_SECONDS}s")
    print(f"[wrapper] Hard timeout: {HARD_TIMEOUT_SECONDS}s")

    print("")
    print("=" * 80)
    print("[wrapper] PROMPT DUMP")
    print("=" * 80)
    print("")
    print("--- COMPLETION INSTRUCTION (passed via --print) ---")
    print(completion_instruction)
    print("--- END COMPLETION INSTRUCTION ---")
    print("")
    print("--- FULL COMMAND ---")
    cmd_display = ["cursor-agent", "-p", "--output-format", "json", "--force"]
    if model:
        cmd_display.extend(["-m", model])
    print(" ".join(cmd_display))
    print("--- END COMMAND ---")
    print("=" * 80)
    print("")

    # Verify CLI is available (fail fast if not)
    check_result = subprocess.run(["which", "cursor-agent"], capture_output=True, text=True)
    if check_result.returncode != 0:
        print("[wrapper] WARNING: cursor-agent not found in PATH!")
        print("[wrapper] Attempting to run anyway in case it's available...")
    else:
        print(f"[wrapper] Cursor CLI found at: {check_result.stdout.strip()}")

    print("[wrapper] Starting Cursor Agent...")
    print("[wrapper] ========================================")
    sys.stdout.flush()
    sys.stderr.flush()

    # Use Popen with idle-timeout watchdog (ADR-016)
    process = subprocess.Popen(
        cmd,
        cwd="/testbed",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    last_output_time = [time.time()]
    start_time = time.time()

    def watchdog():
        """Monitor for idle timeout and hard timeout."""
        while process.poll() is None:
            now = time.time()
            idle_duration = now - last_output_time[0]
            total_duration = now - start_time

            # Check hard timeout
            if total_duration > HARD_TIMEOUT_SECONDS:
                print(f"\n[wrapper] Hard timeout reached ({HARD_TIMEOUT_SECONDS}s), sending SIGTERM")
                process.terminate()
                time.sleep(5)
                if process.poll() is None:
                    print("[wrapper] Process did not terminate, sending SIGKILL")
                    process.kill()
                return

            # Check idle timeout
            if idle_duration > IDLE_TIMEOUT_SECONDS:
                print(f"\n[wrapper] Cursor idle for >{IDLE_TIMEOUT_SECONDS}s, sending SIGTERM")
                process.terminate()
                time.sleep(5)
                if process.poll() is None:
                    print("[wrapper] Process did not terminate, sending SIGKILL")
                    process.kill()
                return

            time.sleep(5)

    watchdog_thread = threading.Thread(target=watchdog, daemon=True)
    watchdog_thread.start()

    # Stream output line by line
    for line in iter(process.stdout.readline, ''):
        if line:
            last_output_time[0] = time.time()
            print(line, end='', flush=True)

    # Wait for process to complete
    process.wait()

    print("\n[wrapper] ========================================")
    print(f"[wrapper] Cursor CLI exited with code: {process.returncode}")
    duration = time.time() - start_time
    print(f"[wrapper] Total duration: {duration:.1f}s")

    sys.exit(process.returncode)


if __name__ == "__main__":
    main()
