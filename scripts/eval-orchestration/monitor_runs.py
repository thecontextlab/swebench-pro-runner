#!/usr/bin/env python3
"""Monitor SWE-bench Pro evaluation runs in GitHub Actions.

Replaces: monitor_opus46_mcp.sh, monitor_webclients_codex.sh,
and ~8 other monitor scripts.

Polls workflow runs and reports completed/in-progress/queued/failed status
with per-repo breakdown.
"""

import argparse
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime


def fetch_runs(limit=200):
    """Fetch recent workflow runs from GitHub Actions."""
    result = subprocess.run(
        ["gh", "run", "list", "--workflow=swebench-eval.yml",
         f"--limit={limit}",
         "--json", "databaseId,displayTitle,status,conclusion,createdAt"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Error fetching runs: {result.stderr}", file=sys.stderr)
        return []
    return json.loads(result.stdout)


def filter_runs(runs, start_date=None, model=None, agent=None, mcp=None, repo=None):
    """Filter runs by criteria."""
    filtered = []
    for run in runs:
        created = run.get("createdAt", "")
        title = run.get("displayTitle", "")

        if start_date and created < start_date:
            continue
        if model and model not in title:
            continue
        if agent and f"| {agent} |" not in title and f"| {agent}" not in title:
            continue
        if mcp is not None:
            mcp_str = f"MCP:{str(mcp).lower()}"
            if mcp_str not in title.lower():
                continue
        if repo and repo not in title:
            continue

        filtered.append(run)
    return filtered


def display_status(runs, label=""):
    """Display status summary of runs."""
    if label:
        print(f"\n{'='*60}")
        print(f" {label}")
        print(f"{'='*60}")

    total = len(runs)
    print(f"\nTotal runs: {total}")

    if not runs:
        return

    # Status breakdown
    status_counts = Counter(r.get("status", "unknown") for r in runs)
    print(f"\nStatus:")
    for status, count in sorted(status_counts.items()):
        pct = count / total * 100
        print(f"  {status:15s} {count:4d}  ({pct:.1f}%)")

    # Conclusion breakdown (only for completed runs)
    completed = [r for r in runs if r.get("status") == "completed"]
    if completed:
        conclusion_counts = Counter(r.get("conclusion", "unknown") for r in completed)
        print(f"\nConclusions (completed only):")
        for conclusion, count in sorted(conclusion_counts.items()):
            print(f"  {conclusion:15s} {count:4d}")

    # Per-repo breakdown
    repo_status = defaultdict(lambda: Counter())
    for r in runs:
        title = r.get("displayTitle", "")
        # Extract repo from displayTitle (first field before |)
        parts = title.split("|")
        repo_name = parts[0].strip() if parts else "unknown"
        status = r.get("status", "unknown")
        repo_status[repo_name][status] += 1

    if len(repo_status) > 1:
        print(f"\nPer-Repository Breakdown:")
        print(f"  {'Repository':20s} {'Completed':>10s} {'In Progress':>12s} {'Queued':>8s} {'Failed':>8s}")
        print(f"  {'-'*20} {'-'*10} {'-'*12} {'-'*8} {'-'*8}")
        for repo_name in sorted(repo_status.keys()):
            counts = repo_status[repo_name]
            completed_count = counts.get("completed", 0)
            in_progress = counts.get("in_progress", 0)
            queued = counts.get("queued", 0)
            # Count failures from conclusions
            repo_completed = [r for r in runs
                              if r.get("status") == "completed"
                              and r.get("displayTitle", "").split("|")[0].strip() == repo_name]
            failed = sum(1 for r in repo_completed if r.get("conclusion") == "failure")
            print(f"  {repo_name:20s} {completed_count:10d} {in_progress:12d} {queued:8d} {failed:8d}")

    # Show in-progress runs
    in_progress = [r for r in runs if r.get("status") == "in_progress"]
    if in_progress:
        print(f"\nCurrently Running ({len(in_progress)}):")
        for r in in_progress[:20]:  # Show first 20
            print(f"  {r.get('displayTitle', 'unknown')}")
        if len(in_progress) > 20:
            print(f"  ... and {len(in_progress) - 20} more")

    # Progress percentage (if we know the target)
    success_count = sum(1 for r in runs
                        if r.get("status") == "completed" and r.get("conclusion") == "success")
    print(f"\nSuccessfully completed: {success_count}/{total}")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor SWE-bench Pro evaluation runs in GitHub Actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # One-shot status of today's Codex runs
  python3 monitor_runs.py --start-date 2026-02-21 --model gpt-5.2-codex

  # Watch Claude opus runs with 60s refresh
  python3 monitor_runs.py --start-date 2026-02-21 --model claude-opus-4-6 \\
    --watch --interval 60

  # Monitor specific repo
  python3 monitor_runs.py --start-date 2026-02-21 --repo flipt --agent codex
""",
    )
    parser.add_argument("--start-date", help="Filter runs from this date (YYYY-MM-DD)")
    parser.add_argument("--model", help="Filter by model string in displayTitle")
    parser.add_argument("--agent", help="Filter by agent name")
    parser.add_argument("--mcp", choices=["true", "false"], help="Filter by MCP flag")
    parser.add_argument("--repo", help="Filter by repository name")
    parser.add_argument("--limit", type=int, default=200, help="Max runs to fetch (default: 200)")
    parser.add_argument("--watch", action="store_true", help="Continuously poll for updates")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds (default: 60)")
    args = parser.parse_args()

    mcp_bool = None
    if args.mcp is not None:
        mcp_bool = args.mcp == "true"

    label_parts = []
    if args.model:
        label_parts.append(args.model)
    if args.agent:
        label_parts.append(args.agent)
    if args.mcp:
        label_parts.append(f"MCP:{args.mcp}")
    if args.repo:
        label_parts.append(args.repo)
    label = " | ".join(label_parts) if label_parts else "All Runs"

    while True:
        runs = fetch_runs(args.limit)
        filtered = filter_runs(
            runs,
            start_date=args.start_date,
            model=args.model,
            agent=args.agent,
            mcp=mcp_bool,
            repo=args.repo,
        )

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        display_status(filtered, f"{label} — {timestamp}")

        if not args.watch:
            break

        # Check if all runs are complete
        in_progress = [r for r in filtered if r.get("status") in ("in_progress", "queued")]
        if not in_progress:
            print(f"\nAll runs completed. Stopping watch.")
            break

        print(f"\nRefreshing in {args.interval}s... (Ctrl+C to stop)")
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")
            break


if __name__ == "__main__":
    main()
