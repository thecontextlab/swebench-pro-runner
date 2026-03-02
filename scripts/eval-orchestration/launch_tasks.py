#!/usr/bin/env python3
"""Launch SWE-bench Pro evaluation tasks via GitHub Actions.

Replaces: launch_opus46_baseline.sh, launch_codex52_baseline.sh,
rerun_codex52_*.sh, and ~20 other launch/rerun scripts.

Reads a task file (pipe-delimited: repo|task_id) and dispatches workflow runs
with configurable model, agent, MCP settings, and rate-limit-aware delays.
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime


def load_tasks(task_file):
    """Load tasks from pipe-delimited file.

    Format: repo|task_id
    Lines starting with # are comments. Empty lines are skipped.
    """
    tasks = []
    with open(task_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|", 1)
            if len(parts) != 2:
                print(f"WARNING: skipping malformed line: {line}", file=sys.stderr)
                continue
            repo, task_id = parts[0].strip(), parts[1].strip()
            tasks.append((repo, task_id))
    return tasks


def load_already_launched(log_file):
    """Parse launch log to find already-dispatched tasks (for resume)."""
    launched = set()
    if not log_file or not os.path.exists(log_file):
        return launched
    with open(log_file, errors="replace") as f:
        for line in f:
            if "LAUNCHED:" in line:
                # Format: "LAUNCHED: repo|task_id"
                parts = line.split("LAUNCHED:", 1)[1].strip()
                launched.add(parts)
    return launched


def launch_task(repo, task_id, model, agent, mcp, dry_run=False):
    """Dispatch a single workflow run. Returns True on success."""
    mcp_str = "true" if mcp else "false"
    cmd = [
        "gh", "workflow", "run", "swebench-eval.yml",
        "-f", f"repo={repo}",
        "-f", f"task={task_id}",
        "-f", f"agent={agent}",
        "-f", f"model={model}",
        "-f", f"enable_mcp={mcp_str}",
    ]

    if dry_run:
        print(f"  [DRY RUN] {' '.join(cmd)}")
        return True

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Launch SWE-bench Pro evaluation tasks via GitHub Actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Task file format (pipe-delimited, one per line):
  ansible|ansible__ansible-12734fa21c08a...
  element-web|element-hq__element-web-4c6b0d35...
  # Comments and empty lines are skipped

Examples:
  # Launch 100 Codex baseline tasks with 2-minute delays
  python3 launch_tasks.py --task-file tasks.txt --model gpt-5.2-codex \\
    --agent codex --mcp false --delay 120

  # Dry-run to verify task list
  python3 launch_tasks.py --task-file rerun_tasks.txt --model claude-opus-4-6 \\
    --agent claude --delay 5 --dry-run

  # Resume a partially-completed launch
  python3 launch_tasks.py --task-file tasks.txt --model gpt-5.2-codex \\
    --agent codex --delay 120 --log-file launch.log
""",
    )
    parser.add_argument("--task-file", required=True, help="Path to pipe-delimited task file (repo|task_id)")
    parser.add_argument("--model", required=True, help="Model to use (e.g. gpt-5.2-codex, claude-opus-4-6)")
    parser.add_argument("--agent", required=True, help="Agent name (claude, codex, gemini)")
    parser.add_argument("--mcp", choices=["true", "false"], default="false", help="Enable MCP (default: false)")
    parser.add_argument("--delay", type=int, default=5, help="Seconds between launches (default: 5)")
    parser.add_argument("--log-file", help="Log file for tracking launched tasks (enables resume)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    args = parser.parse_args()

    mcp_bool = args.mcp == "true"
    tasks = load_tasks(args.task_file)
    print(f"Loaded {len(tasks)} tasks from {args.task_file}")

    # Resume support: skip already-launched tasks
    already_launched = load_already_launched(args.log_file)
    if already_launched:
        print(f"Found {len(already_launched)} already-launched tasks in log")

    log_fh = None
    if args.log_file:
        log_fh = open(args.log_file, "a")

    success = 0
    failure = 0
    skipped = 0
    total = len(tasks)

    for i, (repo, task_id) in enumerate(tasks):
        task_key = f"{repo}|{task_id}"

        if task_key in already_launched:
            print(f"[{i+1}/{total}] SKIP (already launched): {repo} - {task_id}")
            skipped += 1
            continue

        print(f"[{i+1}/{total}] Launching: {repo} - {task_id}")

        if launch_task(repo, task_id, args.model, args.agent, mcp_bool, args.dry_run):
            success += 1
            if log_fh:
                log_fh.write(f"{datetime.now().isoformat()} LAUNCHED: {task_key}\n")
                log_fh.flush()
        else:
            failure += 1
            print(f"  FAILED to launch!")
            if log_fh:
                log_fh.write(f"{datetime.now().isoformat()} FAILED: {task_key}\n")
                log_fh.flush()

        # Rate-limit delay (skip on last task)
        if i < total - 1 and not args.dry_run:
            time.sleep(args.delay)

    if log_fh:
        log_fh.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"Launch Summary")
    print(f"{'='*60}")
    print(f"Total tasks: {total}")
    print(f"Launched: {success}")
    print(f"Failed: {failure}")
    print(f"Skipped (already launched): {skipped}")
    if args.dry_run:
        print("(DRY RUN - no tasks were actually dispatched)")


if __name__ == "__main__":
    main()
