#!/usr/bin/env python3
"""Launch regression tests for resolved tasks via GitHub Actions.

Scans an artifact directory for resolved tasks with non-empty changes.patch,
and dispatches regression-test.yml workflow runs with the original run ID
so the regression workflow can download the patch artifact.

Usage:
    python3 launch_regression_tests.py \\
        --artifact-dir /path/to/eval-bestof3-20260221 \\
        --task-yaml-dir datasets \\
        --run-id 12345678 \\
        --delay 30

    # Dry-run to see what would be launched
    python3 launch_regression_tests.py \\
        --artifact-dir /path/to/eval-bestof3-20260221 \\
        --task-yaml-dir datasets \\
        --run-id 12345678 \\
        --dry-run
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _utils import (
    get_repo_from_folder, load_result, get_task_id,
    get_repo_from_task_id, load_pass_to_pass,
)


def scan_resolved_tasks(artifact_dir):
    """Scan artifact directory for resolved tasks with non-empty patches.

    Returns list of dicts with keys: folder, repo, task_id, patch_path, patch_size.
    """
    tasks = []
    folders = sorted([
        d for d in os.listdir(artifact_dir)
        if os.path.isdir(os.path.join(artifact_dir, d))
        and not d.startswith(".")
    ])

    for folder in folders:
        path = os.path.join(artifact_dir, folder)
        result = load_result(path)
        if result is None:
            continue

        if not result.get("resolved", False):
            continue

        task_id = get_task_id(result)
        if not task_id:
            continue

        repo = get_repo_from_task_id(task_id)
        if not repo:
            repo = get_repo_from_folder(folder)

        patch_path = os.path.join(path, "changes.patch")
        if not os.path.exists(patch_path):
            continue

        patch_size = os.path.getsize(patch_path)

        tasks.append({
            "folder": folder,
            "repo": repo,
            "task_id": task_id,
            "patch_path": patch_path,
            "patch_size": patch_size,
        })

    return tasks


def launch_regression(repo, task_id, run_id, dry_run=False):
    """Dispatch regression-test.yml workflow run. Returns True on success."""
    cmd = [
        "gh", "workflow", "run", "regression-test.yml",
        "-f", f"repo={repo}",
        "-f", f"task={task_id}",
        "-f", f"patch_run_id={run_id}",
    ]

    if dry_run:
        print(f"  [DRY RUN] {' '.join(cmd)}")
        return True

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR launching workflow: {result.stderr}", file=sys.stderr)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Launch regression tests for resolved tasks via GitHub Actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Launch regression tests for all resolved tasks
  python3 launch_regression_tests.py \\
    --artifact-dir ./eval-bestof3-20260221 \\
    --task-yaml-dir datasets --run-id 12345678 --delay 30

  # Only tasks with pass_to_pass tests
  python3 launch_regression_tests.py \\
    --artifact-dir ./eval-bestof3-20260221 \\
    --task-yaml-dir datasets --run-id 12345678 --only-with-p2p

  # Dry-run (no dispatches)
  python3 launch_regression_tests.py \\
    --artifact-dir ./eval-bestof3-20260221 \\
    --task-yaml-dir datasets --run-id 12345678 --dry-run
""",
    )
    parser.add_argument("--artifact-dir", required=True,
                        help="Directory containing artifact folders (each with result.json, changes.patch)")
    parser.add_argument("--task-yaml-dir", required=True,
                        help="Root datasets directory (e.g. datasets/)")
    parser.add_argument("--run-id", required=True,
                        help="GitHub Actions run ID that produced the artifacts (used for patch download)")
    parser.add_argument("--only-resolved", action="store_true", default=True,
                        help="Only include resolved tasks (default: true)")
    parser.add_argument("--only-with-p2p", action="store_true",
                        help="Only include tasks that have non-empty pass_to_pass lists")
    parser.add_argument("--delay", type=int, default=30,
                        help="Seconds between launches (default: 30)")
    parser.add_argument("--log-file", help="Log file for tracking launched tasks (enables resume)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without executing")
    args = parser.parse_args()

    if not os.path.isdir(args.artifact_dir):
        print(f"Error: {args.artifact_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Scan for resolved tasks
    tasks = scan_resolved_tasks(args.artifact_dir)
    print(f"Found {len(tasks)} resolved tasks with patches")

    # Annotate with p2p info
    p2p_stats = {"with_p2p": 0, "without_p2p": 0, "total_p2p_tests": 0}
    for task in tasks:
        p2p_list = load_pass_to_pass(args.task_yaml_dir, task["task_id"])
        task["p2p_count"] = len(p2p_list) if p2p_list else 0
        task["has_p2p"] = task["p2p_count"] > 0
        if task["has_p2p"]:
            p2p_stats["with_p2p"] += 1
            p2p_stats["total_p2p_tests"] += task["p2p_count"]
        else:
            p2p_stats["without_p2p"] += 1

    print(f"  With P2P tests: {p2p_stats['with_p2p']} ({p2p_stats['total_p2p_tests']} total p2p tests)")
    print(f"  Without P2P tests: {p2p_stats['without_p2p']} (f2p-only verification)")

    # Filter if requested
    if args.only_with_p2p:
        tasks = [t for t in tasks if t["has_p2p"]]
        print(f"Filtered to {len(tasks)} tasks with P2P tests")

    if not tasks:
        print("No tasks to launch.")
        return

    # Resume support
    already_launched = set()
    if args.log_file and os.path.exists(args.log_file):
        with open(args.log_file, errors="replace") as f:
            for line in f:
                if "LAUNCHED:" in line:
                    parts = line.split("LAUNCHED:", 1)[1].strip()
                    already_launched.add(parts)
        if already_launched:
            print(f"Found {len(already_launched)} already-launched tasks in log")

    log_fh = None
    if args.log_file:
        log_fh = open(args.log_file, "a")

    # Launch
    success = 0
    failure = 0
    skipped = 0
    total = len(tasks)

    # Per-repo summary for launch manifest
    repo_manifest = {}

    for i, task in enumerate(tasks):
        task_key = f"{task['repo']}|{task['task_id']}"

        if task_key in already_launched:
            print(f"[{i+1}/{total}] SKIP (already launched): {task['repo']} - {task['task_id']}")
            skipped += 1
            continue

        print(f"[{i+1}/{total}] {task['repo']} - {task['task_id']}"
              f" (patch: {task['patch_size']}B, p2p: {task['p2p_count']})")

        # Dispatch regression workflow
        if launch_regression(task["repo"], task["task_id"], args.run_id, args.dry_run):
            success += 1
            if log_fh:
                log_fh.write(f"{datetime.now().isoformat()} LAUNCHED: {task_key}\n")
                log_fh.flush()
            # Track for manifest
            repo_manifest.setdefault(task["repo"], []).append(task)
        else:
            failure += 1
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

    # Per-repo manifest
    if repo_manifest:
        print(f"\nPer-repo breakdown:")
        print(f"  {'Repo':<14} {'Tasks':>5} {'P2P Tests':>10}")
        print(f"  {'-'*14} {'-'*5} {'-'*10}")
        for repo in sorted(repo_manifest.keys()):
            repo_tasks = repo_manifest[repo]
            total_p2p = sum(t["p2p_count"] for t in repo_tasks)
            print(f"  {repo:<14} {len(repo_tasks):>5} {total_p2p:>10}")


if __name__ == "__main__":
    main()
