#!/usr/bin/env python3
"""Validate SWE-bench Pro evaluation artifacts for completeness and consistency.

Replaces: analyze_experiment_artifacts.py and infrastructure audit logic.

Checks result.json validity, agent.log non-emptiness, pre_verification.log
existence, rate limiting detection, and result consistency.
"""

import argparse
import json
import os
import sys
from collections import defaultdict

# Add parent dir for shared utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _utils import get_repo_from_folder, scan_agent_log, load_result, extract_metrics


REQUIRED_FILES = [
    "result.json",
    "agent.log",
    "pre_verification.log",
    "verification.log",
]

MIN_FILE_SIZES = {
    "result.json": 100,
    "agent.log": 500,
    "pre_verification.log": 50,
    "verification.log": 50,
}


def validate_folder(folder_path):
    """Validate a single artifact folder. Returns dict of issues found."""
    issues = []
    folder_name = os.path.basename(folder_path)

    # Check required files
    for fname in REQUIRED_FILES:
        fpath = os.path.join(folder_path, fname)
        if not os.path.exists(fpath):
            issues.append(f"missing:{fname}")
        elif os.path.getsize(fpath) < MIN_FILE_SIZES.get(fname, 0):
            issues.append(f"too-small:{fname}")

    # Load and validate result.json
    result = load_result(folder_path)
    if result is None:
        issues.append("invalid-result-json")
    else:
        # Check required fields
        if "resolved" not in result:
            issues.append("missing-resolved-field")
        if "task_id" not in result and "task" not in result:
            issues.append("missing-task-id")

    # Scan agent.log for issues
    agent_log = os.path.join(folder_path, "agent.log")
    log_flags = scan_agent_log(agent_log)

    # Check pre-verification: tests should FAIL before agent runs
    pre_verif = os.path.join(folder_path, "pre_verification.log")
    pre_verif_ok = None
    if os.path.exists(pre_verif):
        try:
            with open(pre_verif, "r", errors="replace") as f:
                content = f.read()
            # Pre-verification should show test failures (exit code != 0)
            if "exit code: 0" in content.lower() or "all tests passed" in content.lower():
                issues.append("pre-verification-passed")
                pre_verif_ok = False
            else:
                pre_verif_ok = True
        except OSError:
            pass

    # Consistency check: result.json resolved vs verification.log
    verif_log = os.path.join(folder_path, "verification.log")
    if result and os.path.exists(verif_log):
        try:
            with open(verif_log, "r", errors="replace") as f:
                verif_content = f.read()
            resolved_in_result = result.get("resolved", False)
            verif_passed = "exit code: 0" in verif_content.lower() or "pass" in verif_content.lower()
            if resolved_in_result and not verif_passed:
                issues.append("result-verif-mismatch:resolved-but-verif-failed")
        except OSError:
            pass

    return {
        "folder": folder_name,
        "repo": get_repo_from_folder(folder_name),
        "issues": issues,
        "rate_limited": log_flags["rate_limited"],
        "turn_failed": log_flags["turn_failed"],
        "resolved": result.get("resolved", False) if result else None,
        "pre_verif_ok": pre_verif_ok,
        "has_result": result is not None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate SWE-bench Pro evaluation artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Validate all artifacts in a directory
  python3 validate_artifacts.py --artifact-dir ./eval-codex52-bestof3-20260221

  # Validate and export JSON report
  python3 validate_artifacts.py --artifact-dir ./eval-opus46 --output-json report.json
""",
    )
    parser.add_argument("--artifact-dir", required=True, help="Directory containing artifact folders")
    parser.add_argument("--output-json", help="Write validation report as JSON to this path")
    args = parser.parse_args()

    if not os.path.isdir(args.artifact_dir):
        print(f"Error: {args.artifact_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Find artifact folders (skip non-directories and special files)
    folders = sorted([
        d for d in os.listdir(args.artifact_dir)
        if os.path.isdir(os.path.join(args.artifact_dir, d))
        and not d.startswith(".")
    ])

    if not folders:
        print("No artifact folders found.")
        return

    print(f"Validating {len(folders)} artifact folders in {args.artifact_dir}\n")

    results = []
    for folder in folders:
        path = os.path.join(args.artifact_dir, folder)
        result = validate_folder(path)
        results.append(result)

    # Summary statistics
    total = len(results)
    valid = sum(1 for r in results if not r["issues"])
    with_issues = sum(1 for r in results if r["issues"])
    rate_limited = sum(1 for r in results if r["rate_limited"])
    turn_failed = sum(1 for r in results if r["turn_failed"])
    resolved = sum(1 for r in results if r["resolved"])
    missing_result = sum(1 for r in results if not r["has_result"])

    # Display summary
    print(f"{'='*60}")
    print(f" Validation Summary")
    print(f"{'='*60}")
    print(f"Total folders:       {total}")
    print(f"Valid (no issues):   {valid}")
    print(f"With issues:         {with_issues}")
    print(f"Rate limited:        {rate_limited}")
    print(f"Turn failed:         {turn_failed}")
    print(f"Resolved:            {resolved}/{total} ({resolved/total*100:.1f}%)")
    print(f"Missing result.json: {missing_result}")

    # Per-repo breakdown
    repo_stats = defaultdict(lambda: {"total": 0, "resolved": 0, "issues": 0, "rate_limited": 0})
    for r in results:
        repo = r["repo"]
        repo_stats[repo]["total"] += 1
        if r["resolved"]:
            repo_stats[repo]["resolved"] += 1
        if r["issues"]:
            repo_stats[repo]["issues"] += 1
        if r["rate_limited"]:
            repo_stats[repo]["rate_limited"] += 1

    print(f"\nPer-Repository:")
    print(f"  {'Repository':20s} {'Total':>6s} {'Resolved':>9s} {'Issues':>7s} {'RateLtd':>8s}")
    print(f"  {'-'*20} {'-'*6} {'-'*9} {'-'*7} {'-'*8}")
    for repo in sorted(repo_stats.keys()):
        s = repo_stats[repo]
        print(f"  {repo:20s} {s['total']:6d} {s['resolved']:9d} {s['issues']:7d} {s['rate_limited']:8d}")

    # Show folders with issues
    problem_folders = [r for r in results if r["issues"]]
    if problem_folders:
        print(f"\nFolders with Issues ({len(problem_folders)}):")
        for r in problem_folders:
            issues_str = ", ".join(r["issues"])
            print(f"  {r['folder']}: {issues_str}")

    # JSON output
    if args.output_json:
        report = {
            "summary": {
                "total": total,
                "valid": valid,
                "with_issues": with_issues,
                "rate_limited": rate_limited,
                "turn_failed": turn_failed,
                "resolved": resolved,
            },
            "per_repo": dict(repo_stats),
            "details": results,
        }
        with open(args.output_json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nJSON report written: {args.output_json}")


if __name__ == "__main__":
    main()
