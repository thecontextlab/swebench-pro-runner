#!/usr/bin/env python3
"""Extract failing tasks from evaluation artifacts for reruns.

Replaces: ad-hoc Python one-liners for identifying failing tasks.

Reads an artifact directory, finds tasks where resolved=false, and outputs
them in launch-ready format or CSV with metrics.
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _utils import get_repo_from_folder, get_hash_part, load_result, extract_metrics, scan_agent_log, get_task_id


def main():
    parser = argparse.ArgumentParser(
        description="Extract failing tasks from evaluation artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Extract failing tasks in launch format (for launch_tasks.py)
  python3 extract_failing_tasks.py --artifact-dir ./eval-codex52 --format launch

  # Extract only rate-limited failures
  python3 extract_failing_tasks.py --artifact-dir ./eval-codex52 \\
    --rate-limited-only --format launch > rerun_tasks.txt

  # CSV with metrics for analysis
  python3 extract_failing_tasks.py --artifact-dir ./eval-codex52 --format csv

  # Exclude known broken tasks
  python3 extract_failing_tasks.py --artifact-dir ./eval-codex52 \\
    --exclude-broken f8e7fea0becae25ae20606f1422068137189fe9e --format launch
""",
    )
    parser.add_argument("--artifact-dir", required=True, help="Directory containing artifact folders")
    parser.add_argument("--format", choices=["launch", "csv"], default="launch",
                        help="Output format: launch (pipe-delimited for launch_tasks.py) or csv")
    parser.add_argument("--rate-limited-only", action="store_true",
                        help="Only include tasks that were rate-limited")
    parser.add_argument("--exclude-broken", nargs="*", default=[],
                        help="Hash parts of broken tasks to exclude")
    parser.add_argument("--include-all", action="store_true",
                        help="Include all failing tasks (ignore rate-limit filter)")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    if not os.path.isdir(args.artifact_dir):
        print(f"Error: {args.artifact_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    broken_set = set(args.exclude_broken)

    # Scan artifact folders
    folders = sorted([
        d for d in os.listdir(args.artifact_dir)
        if os.path.isdir(os.path.join(args.artifact_dir, d))
        and not d.startswith(".")
    ])

    failing = []

    for folder in folders:
        path = os.path.join(args.artifact_dir, folder)
        hash_part = get_hash_part(folder)

        # Skip broken tasks
        if hash_part in broken_set:
            continue

        result = load_result(path)
        if result is None:
            continue

        # Only failing tasks
        if result.get("resolved", False):
            continue

        repo = get_repo_from_folder(folder)
        agent_log = os.path.join(path, "agent.log")
        log_flags = scan_agent_log(agent_log)

        # Rate-limit filter
        if args.rate_limited_only and not log_flags["rate_limited"]:
            continue

        task_id = get_task_id(result)
        metrics = extract_metrics(result)

        failing.append({
            "repo": repo,
            "task_id": task_id,
            "hash_part": hash_part,
            "rate_limited": log_flags["rate_limited"],
            "turn_failed": log_flags["turn_failed"],
            "cost": metrics["total_cost_usd"],
            "duration": metrics["duration_seconds"],
            "tool_calls": metrics["total_tool_calls"],
            "turns": metrics["num_turns"],
        })

    # Output
    out = open(args.output, "w") if args.output else sys.stdout

    if args.format == "launch":
        # Pipe-delimited format compatible with launch_tasks.py
        for task in sorted(failing, key=lambda t: (t["repo"], t["task_id"])):
            out.write(f"{task['repo']}|{task['task_id']}\n")
    elif args.format == "csv":
        writer = csv.DictWriter(out, fieldnames=[
            "repo", "task_id", "hash_part", "rate_limited", "turn_failed",
            "cost", "duration", "tool_calls", "turns",
        ])
        writer.writeheader()
        for task in sorted(failing, key=lambda t: (t["repo"], t["task_id"])):
            writer.writerow(task)

    if args.output:
        out.close()

    # Summary to stderr so it doesn't interfere with piped output
    print(f"\nExtracted {len(failing)} failing tasks from {len(folders)} total", file=sys.stderr)
    if args.rate_limited_only:
        print(f"  (filtered to rate-limited only)", file=sys.stderr)
    if broken_set:
        print(f"  (excluded {len(broken_set)} broken tasks)", file=sys.stderr)

    # Per-repo breakdown
    repo_counts = {}
    for t in failing:
        repo_counts[t["repo"]] = repo_counts.get(t["repo"], 0) + 1
    if repo_counts:
        print(f"\nPer-repo failing:", file=sys.stderr)
        for repo in sorted(repo_counts.keys()):
            print(f"  {repo}: {repo_counts[repo]}", file=sys.stderr)


if __name__ == "__main__":
    main()
