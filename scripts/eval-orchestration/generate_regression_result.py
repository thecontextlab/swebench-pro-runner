#!/usr/bin/env python3
"""Generate regression_result.json from regression test phase logs.

Runs outside the Docker container (same pattern as extract_metrics.py).
Reads the 4 phase log files + exit code files produced by regression-test.yml
and uses the framework-specific parsers from audit_artifacts.py to determine
true test outcomes (not just exit codes, which can be unreliable).

Environment variables:
    RESULTS_DIR: Path to results directory containing logs and exit files
    TASK_ID: Task identifier
    REPO_NAME: Repository name
    TASK_YAML_DIR: Root datasets directory for loading test lists
    F2P_COUNT: Number of fail_to_pass tests (from workflow)
    P2P_COUNT: Number of pass_to_pass tests (from workflow)
"""

import json
import os
import sys

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _utils import (
    get_repo_from_task_id, get_framework_for_repo,
    load_task_yaml, load_pass_to_pass,
)
from audit_artifacts import parse_verification_log, detect_post_test_crash


def read_exit_code(results_dir, filename):
    """Read an exit code file. Returns int, or None if missing/skip."""
    path = os.path.join(results_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        content = open(path).read().strip()
        if content == "skip":
            return None
        return int(content)
    except (ValueError, OSError):
        return None


def read_log(results_dir, filename):
    """Read a log file. Returns text content or empty string."""
    path = os.path.join(results_dir, filename)
    if not os.path.exists(path):
        return ""
    try:
        with open(path, errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def parse_phase(framework, test_list, log_text, phase_name):
    """Parse a single test phase log and return phase result dict.

    Args:
        framework: Test framework name (pytest, go, jest, etc.)
        test_list: List of expected test identifiers
        log_text: Raw log output text
        phase_name: Name for diagnostics (e.g. 'p2p_pre')

    Returns:
        Dict with exit_code, tests_expected, tests_passed, tests_failed,
        tests_not_found, verdict, and crash_type fields.
    """
    if not test_list:
        return {
            "tests_expected": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_not_found": 0,
            "verdict": "skip",
            "crash_type": None,
        }

    if not log_text or log_text.startswith("No pass_to_pass tests") or \
       log_text.startswith("Patch application failed"):
        return {
            "tests_expected": len(test_list),
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_not_found": len(test_list),
            "verdict": "skip",
            "crash_type": None,
        }

    # Parse with framework-specific parser
    outcomes = parse_verification_log(framework, test_list, log_text)

    passed = [t for t, o in outcomes.items() if o == "PASSED"]
    failed = [t for t, o in outcomes.items() if o in ("FAILED", "NOT_EXIST")]
    not_found = [t for t, o in outcomes.items() if o == "NOT_FOUND"]
    build_fail = [t for t, o in outcomes.items() if o == "BUILD_FAIL"]

    crash_type = detect_post_test_crash(log_text, framework)

    # Determine verdict
    all_passed = len(failed) == 0 and len(not_found) == 0 and len(build_fail) == 0
    if all_passed:
        verdict = "ok"
    elif crash_type and len(passed) == len(test_list):
        # All tests passed but process crashed after (e.g. X11 crash)
        verdict = "ok"
    elif len(build_fail) > 0 and len(failed) == 0 and len(not_found) == 0:
        # Tests couldn't run due to build failure in unrelated packages
        verdict = "build_fail"
    else:
        verdict = "fail"

    return {
        "tests_expected": len(test_list),
        "tests_passed": len(passed),
        "tests_failed": len(failed),
        "tests_not_found": len(not_found),
        "tests_build_fail": len(build_fail),
        "verdict": verdict,
        "crash_type": crash_type,
        "passed_tests": passed,
        "failed_tests": failed,
        "not_found_tests": not_found,
        "build_fail_tests": build_fail,
    }


def main():
    results_dir = os.environ.get("RESULTS_DIR", ".")
    task_id = os.environ.get("TASK_ID", "")
    repo = os.environ.get("REPO_NAME", "")
    task_yaml_dir = os.environ.get("TASK_YAML_DIR", "datasets")

    if not repo and task_id:
        repo = get_repo_from_task_id(task_id) or ""

    framework = get_framework_for_repo(repo)

    # Load test lists from task YAML
    f2p_list = load_task_yaml(task_yaml_dir, task_id) or []
    p2p_list = load_pass_to_pass(task_yaml_dir, task_id) or []

    has_p2p = len(p2p_list) > 0

    # Read exit codes
    patch_exit = read_exit_code(results_dir, ".patch_exit")
    patch_applied = patch_exit == 0 if patch_exit is not None else False

    # Read logs
    p2p_pre_log = read_log(results_dir, "pass_to_pass_pre.log")
    f2p_pre_log = read_log(results_dir, "fail_to_pass_pre.log")
    f2p_post_log = read_log(results_dir, "fail_to_pass_post.log")
    p2p_post_log = read_log(results_dir, "pass_to_pass_post.log")

    # Parse each phase
    p2p_pre = parse_phase(framework, p2p_list, p2p_pre_log, "p2p_pre")
    f2p_pre = parse_phase(framework, f2p_list, f2p_pre_log, "f2p_pre")
    f2p_post = parse_phase(framework, f2p_list, f2p_post_log, "f2p_post")
    p2p_post = parse_phase(framework, p2p_list, p2p_post_log, "p2p_post")

    # Store exit codes from the actual runs
    p2p_pre["exit_code"] = read_exit_code(results_dir, ".p2p_pre_exit")
    f2p_pre["exit_code"] = read_exit_code(results_dir, ".f2p_pre_exit")
    f2p_post["exit_code"] = read_exit_code(results_dir, ".f2p_post_exit")
    p2p_post["exit_code"] = read_exit_code(results_dir, ".p2p_post_exit")

    # Determine aggregate results
    # f2p_resolved: all f2p tests pass post-patch
    f2p_resolved = f2p_post["verdict"] == "ok"

    # p2p_no_regression: all p2p tests pass post-patch (vacuously true if no p2p)
    if not has_p2p:
        p2p_no_regression = True
    else:
        p2p_no_regression = p2p_post["verdict"] == "ok"

    fully_resolved = f2p_resolved and p2p_no_regression

    # Flag pre-patch p2p baseline failures (environment issue, not regression)
    p2p_pre_baseline_failure = (has_p2p and p2p_pre["verdict"] == "fail")

    # Build result
    result = {
        "task_id": task_id,
        "repo": repo,
        "framework": framework,
        "has_p2p": has_p2p,
        "patch_applied": patch_applied,
        "phases": {
            "p2p_pre": _clean_phase(p2p_pre),
            "f2p_pre": _clean_phase(f2p_pre),
            "f2p_post": _clean_phase(f2p_post),
            "p2p_post": _clean_phase(p2p_post),
        },
        "results": {
            "f2p_resolved": f2p_resolved,
            "p2p_no_regression": p2p_no_regression,
            "fully_resolved": fully_resolved,
            "p2p_pre_baseline_failure": p2p_pre_baseline_failure,
        },
    }

    # Write output
    output_path = os.path.join(results_dir, "regression_result.json")
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    # Print summary
    print(f"Regression result for {task_id}:")
    print(f"  Framework: {framework}")
    print(f"  Has P2P: {has_p2p} ({len(p2p_list)} tests)")
    print(f"  Patch applied: {patch_applied}")
    print(f"  F2P resolved: {f2p_resolved}")
    print(f"  P2P no regression: {p2p_no_regression}")
    print(f"  Fully resolved: {fully_resolved}")
    if p2p_pre_baseline_failure:
        print(f"  WARNING: P2P baseline failure (pre-patch p2p tests failed)")
    print(f"  Written to: {output_path}")


def _clean_phase(phase):
    """Remove internal lists from phase dict for JSON output (keep counts only)."""
    result = {
        "exit_code": phase.get("exit_code"),
        "tests_expected": phase["tests_expected"],
        "tests_passed": phase["tests_passed"],
        "tests_failed": phase["tests_failed"],
        "tests_not_found": phase.get("tests_not_found", 0),
        "verdict": phase["verdict"],
        "crash_type": phase.get("crash_type"),
    }
    if phase.get("tests_build_fail", 0) > 0:
        result["tests_build_fail"] = phase["tests_build_fail"]
    return result


if __name__ == "__main__":
    main()
