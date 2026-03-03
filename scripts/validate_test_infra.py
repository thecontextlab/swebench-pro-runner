#!/usr/bin/env python3
"""Validate Go P2P test infrastructure across all repos.

Checks that run_script.sh files correctly handle Go subtests (names containing '/').
Reports tasks where P2P tests would silently fail to execute.

Usage:
    python3 scripts/validate_test_infra.py [--datasets-dir datasets/]
"""

import argparse
import os
import re
import sys
import yaml
from pathlib import Path


# Repo framework classification
GO_REGEX_REPOS = {"vuls", "flipt", "navidrome"}  # Bug 1: regex wrapper
GO_CUSTOM_REPOS = {"teleport"}  # Bug 2: grep pattern
NON_GO_REPOS = {"ansible", "element-web", "NodeBB", "openlibrary", "qutebrowser", "tutanota", "webclients"}


def load_task_yaml(yaml_path: Path) -> dict:
    """Load and return a task YAML file."""
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def check_go_regex_repo(repo: str, tasks_dir: Path) -> list[dict]:
    """Check Bug 1: regex wrapper prevents Go subtest splitting.

    For vuls/flipt/navidrome, the run_script.sh wraps the -run pattern in ^(...)$.
    Go's splitRegexp() splits on '/' only at paren depth 0. The wrapper keeps
    depth >= 1, so subtests like TestConvert/SubName never match.

    Also checks if run_script.sh has the fix applied (uses run_names extraction).
    """
    issues = []

    # Check if run_script.sh has the fix
    run_scripts = list(tasks_dir.glob("*.run_script.sh"))
    if run_scripts:
        with open(run_scripts[0]) as f:
            script_content = f.read()
        # The fix adds a run_names array that extracts parent test names before
        # building the regex. Don't be fooled by func_name in package detection.
        has_fix = "run_names" in script_content
    else:
        has_fix = False

    for yaml_path in sorted(tasks_dir.glob("*.yaml")):
        task = load_task_yaml(yaml_path)
        swebench = task.get("swebench", {})
        p2p_tests = swebench.get("pass_to_pass", [])
        if not p2p_tests:
            continue

        subtest_names = [t for t in p2p_tests if "/" in t]
        if not subtest_names:
            continue

        # Check if parent test is also in the list (which would make it work)
        parents_present = set()
        all_tests = set(p2p_tests)
        for name in subtest_names:
            parent = name.split("/")[0]
            if parent in all_tests:
                parents_present.add(parent)

        # The issue is when subtests are present but run_script.sh doesn't extract parents
        if not has_fix:
            issues.append({
                "task": yaml_path.stem,
                "repo": repo,
                "bug": "regex_wrapper",
                "subtest_count": len(subtest_names),
                "subtests": subtest_names[:5],  # Show first 5
                "parents_in_list": bool(parents_present),
            })

    return issues


def check_go_custom_repo(repo: str, tasks_dir: Path) -> list[dict]:
    """Check Bug 2: grep uses full subtest name for teleport.

    Teleport's run_script.sh does: grep -r "func $test_name" ...
    For test_name="TestDisplay/unix_socket", searches for "func TestDisplay/unix_socket"
    which never exists (Go functions can't have / in names).

    Also checks if run_script.sh has the fix applied.
    """
    issues = []

    run_scripts = list(tasks_dir.glob("*.run_script.sh"))
    if run_scripts:
        with open(run_scripts[0]) as f:
            script_content = f.read()
        has_fix = 'func_name="${test_name%%/*}"' in script_content
    else:
        has_fix = False

    for yaml_path in sorted(tasks_dir.glob("*.yaml")):
        task = load_task_yaml(yaml_path)
        swebench = task.get("swebench", {})
        p2p_tests = swebench.get("pass_to_pass", [])
        if not p2p_tests:
            continue

        subtest_names = [t for t in p2p_tests if "/" in t]
        if not subtest_names:
            continue

        if not has_fix:
            issues.append({
                "task": yaml_path.stem,
                "repo": repo,
                "bug": "grep_pattern",
                "subtest_count": len(subtest_names),
                "subtests": subtest_names[:5],
            })

    return issues


def main():
    parser = argparse.ArgumentParser(description="Validate Go P2P test infrastructure")
    parser.add_argument("--datasets-dir", default="datasets", help="Path to datasets directory")
    args = parser.parse_args()

    datasets_dir = Path(args.datasets_dir)
    if not datasets_dir.exists():
        print(f"ERROR: datasets directory not found: {datasets_dir}", file=sys.stderr)
        sys.exit(1)

    all_issues = []
    summary = {}

    # Check Go regex repos (Bug 1)
    for repo in sorted(GO_REGEX_REPOS):
        tasks_dir = datasets_dir / repo / "tasks"
        if not tasks_dir.exists():
            print(f"  SKIP {repo}: tasks directory not found")
            continue
        issues = check_go_regex_repo(repo, tasks_dir)
        all_issues.extend(issues)
        total_tasks = len(list(tasks_dir.glob("*.yaml")))
        p2p_tasks = len([1 for y in tasks_dir.glob("*.yaml")
                        if load_task_yaml(y).get("swebench", {}).get("pass_to_pass")])
        subtest_tasks = len(issues)
        summary[repo] = {
            "total_tasks": total_tasks,
            "p2p_tasks": p2p_tasks,
            "broken_tasks": subtest_tasks,
            "bug_type": "regex_wrapper",
        }

    # Check Go custom repos (Bug 2)
    for repo in sorted(GO_CUSTOM_REPOS):
        tasks_dir = datasets_dir / repo / "tasks"
        if not tasks_dir.exists():
            print(f"  SKIP {repo}: tasks directory not found")
            continue
        issues = check_go_custom_repo(repo, tasks_dir)
        all_issues.extend(issues)
        total_tasks = len(list(tasks_dir.glob("*.yaml")))
        p2p_tasks = len([1 for y in tasks_dir.glob("*.yaml")
                        if load_task_yaml(y).get("swebench", {}).get("pass_to_pass")])
        subtest_tasks = len(issues)
        summary[repo] = {
            "total_tasks": total_tasks,
            "p2p_tasks": p2p_tasks,
            "broken_tasks": subtest_tasks,
            "bug_type": "grep_pattern",
        }

    # Print summary
    print("=" * 70)
    print("Go P2P Test Infrastructure Validation Report")
    print("=" * 70)
    print()

    total_broken = 0
    for repo, s in sorted(summary.items()):
        status = "PASS" if s["broken_tasks"] == 0 else "FAIL"
        marker = "  " if status == "PASS" else "!!"
        print(f"  {marker} {repo:15s}  {s['total_tasks']:3d} tasks  "
              f"{s['p2p_tasks']:3d} with P2P  "
              f"{s['broken_tasks']:3d} broken  "
              f"[{s['bug_type']}]  {status}")
        total_broken += s["broken_tasks"]

    print()
    print(f"  Total broken tasks: {total_broken}")
    print()

    if all_issues:
        print("-" * 70)
        print("Broken Tasks Detail:")
        print("-" * 70)
        for issue in all_issues:
            print(f"\n  {issue['repo']}/{issue['task']}")
            print(f"    Bug: {issue['bug']}")
            print(f"    Subtests with '/': {issue['subtest_count']}")
            for st in issue["subtests"]:
                print(f"      - {st}")
            if issue["subtest_count"] > 5:
                print(f"      ... and {issue['subtest_count'] - 5} more")
        print()

    if total_broken > 0:
        print(f"RESULT: FAIL - {total_broken} tasks have broken P2P test infrastructure")
        sys.exit(1)
    else:
        print("RESULT: PASS - All P2P test infrastructure is correct")
        sys.exit(0)


if __name__ == "__main__":
    main()
