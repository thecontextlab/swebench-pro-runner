#!/usr/bin/env python3
"""
Parse verification and pre-verification logs from SWE-Bench Pro evaluation.
Determines task resolution based on actual log files, NOT result.json.

Classification logic:
- pre_verification.log: runs F2P tests BEFORE coding fix (should show failures)
- verification.log: runs F2P tests AFTER coding fix (should show passes if resolved)

A task is RESOLVED if:
  - pre_verification shows at least some test failures (confirming bug exists)
  - verification shows all tests passing (confirming fix works)
"""

import os
import re
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Configurable via env var: BASE_DIR=/path/to/archive python3 parse_verification_logs.py
# Falls back to CWD if not set.
BASE_DIR = Path(os.environ.get("BASE_DIR", os.getcwd()))

@dataclass
class LogResult:
    """Parsed result from a single log file."""
    tests_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    tests_errored: int = 0
    framework: str = "unknown"
    has_output: bool = False
    log_exists: bool = False
    raw_summary: str = ""
    parse_notes: str = ""
    has_build_failure: bool = False

@dataclass
class TaskResult:
    """Full result for a task combining pre-verification and verification."""
    folder_name: str
    repo: str
    task_id: str  # short form
    pre_verification: LogResult = field(default_factory=LogResult)
    verification: LogResult = field(default_factory=LogResult)
    classification: str = ""
    notes: str = ""


def detect_repo(folder_name: str) -> str:
    """Extract repo name from folder name."""
    # Format: claude-opus-4-6-{repo}-{commit_hash}...
    prefix = os.environ.get("MODEL_PREFIX", "claude-opus-4-6") + "-"
    rest = folder_name[len(prefix):]
    # Repos can have hyphens (element-web), so we need to match known repos
    known_repos = ["element-web", "NodeBB", "ansible", "flipt", "navidrome",
                   "openlibrary", "qutebrowser", "teleport", "tutanota", "vuls", "webclients"]
    for repo in sorted(known_repos, key=len, reverse=True):  # longest first
        if rest.startswith(repo + "-"):
            return repo
    return rest.split("-")[0]


def extract_task_id(folder_name: str, repo: str) -> str:
    """Extract short task ID from folder name."""
    prefix = f"{os.environ.get("MODEL_PREFIX", "claude-opus-4-6")}-{repo}-"
    rest = folder_name[len(prefix):]
    commit = rest[:8]
    return f"{repo}-{commit}"


def parse_pytest_log(content: str) -> LogResult:
    """Parse pytest output."""
    result = LogResult(framework="pytest", has_output=True, log_exists=True)

    # Look for the final summary line like "1 passed in 0.23s" or "1 failed in 0.38s"
    # or "1 failed, 2 passed in 1.5s" etc.
    # The key pattern is the last line matching ====...====
    summary_patterns = [
        # "X passed, Y failed, Z error in Ns"
        r'=+\s*(.*?)\s*=+\s*$',
    ]

    lines = content.strip().split('\n')
    summary_line = ""
    for line in reversed(lines):
        line = line.strip()
        if re.match(r'=+.*=+', line):
            summary_line = line
            break

    if summary_line:
        result.raw_summary = summary_line
        # Extract counts from summary like "1 passed, 2 failed, 3 errors in 0.5s"
        passed = re.search(r'(\d+)\s+passed', summary_line)
        failed = re.search(r'(\d+)\s+failed', summary_line)
        error = re.search(r'(\d+)\s+errors?(?:\s+in|\s*=)', summary_line)
        skipped = re.search(r'(\d+)\s+skipped', summary_line)
        warnings_match = re.search(r'(\d+)\s+warnings?', summary_line)
        rerun = re.search(r'(\d+)\s+rerun', summary_line)

        if passed:
            result.tests_passed = int(passed.group(1))
        if failed:
            result.tests_failed = int(failed.group(1))
        if error:
            result.tests_errored = int(error.group(1))
        if skipped:
            result.tests_skipped = int(skipped.group(1))

        result.tests_total = result.tests_passed + result.tests_failed + result.tests_errored

        # If only warnings and no test results, the tests didn't actually run
        if result.tests_total == 0 and warnings_match and not passed and not failed and not error:
            result.parse_notes = "only warnings, no tests ran"
    else:
        # No summary line found - check for pytest crashes or collection errors
        if "test session starts" not in content:
            # pytest didn't even start a test session
            if "Traceback" in content or "TypeError" in content or "ImportError" in content:
                result.parse_notes = "pytest crash before session start"
                result.has_build_failure = True
            elif "ModuleNotFoundError" in content:
                result.parse_notes = "module import error"
                result.has_build_failure = True
            else:
                result.parse_notes = "no pytest session found"
        elif "no tests ran" in content:
            result.parse_notes = "no tests ran"
        elif "ERROR collecting" in content or "ImportError" in content:
            result.parse_notes = "collection error"
            result.has_build_failure = True
        elif "error" in content.lower():
            result.parse_notes = "error in output"

    return result


def parse_go_test_log(content: str) -> LogResult:
    """Parse Go test output (go test, including ginkgo)."""
    result = LogResult(framework="go-test", has_output=True, log_exists=True)

    # Check for Ginkgo framework (navidrome)
    if "Running Suite:" in content or "Ran " in content and "Specs" in content:
        return parse_ginkgo_log(content)

    # Count --- PASS: and --- FAIL: lines (top-level only, not nested)
    pass_count = 0
    fail_count = 0

    for line in content.split('\n'):
        line = line.strip()
        # Only count top-level tests (not indented subtests)
        if re.match(r'^--- PASS:', line):
            pass_count += 1
        elif re.match(r'^--- FAIL:', line):
            fail_count += 1

    # Also check for package-level FAIL (build failures)
    build_fail_lines = re.findall(r'FAIL\s+\S+\s+\[build failed\]', content)
    setup_fail_lines = re.findall(r'FAIL\s+\S+\s+\[setup failed\]', content)
    if build_fail_lines or setup_fail_lines:
        result.has_build_failure = True
        if pass_count == 0 and fail_count == 0:
            # Pure build failure, no tests ran
            result.parse_notes = "build failure"
            result.tests_failed = len(build_fail_lines) + len(setup_fail_lines)
            result.tests_total = result.tests_failed
            return result

    # Check for teleport-style wrapper output
    teleport_pass = len(re.findall(r'Test passed \(expected', content))
    teleport_fail = len(re.findall(r'Test failed \(expected', content))
    if teleport_pass > 0 or teleport_fail > 0:
        # Use teleport wrapper counts if we have them and they're larger
        if teleport_pass + teleport_fail > pass_count + fail_count:
            pass_count = teleport_pass
            fail_count = teleport_fail

    result.tests_passed = pass_count
    result.tests_failed = fail_count
    result.tests_total = pass_count + fail_count

    # Build summary
    ok_packages = len(re.findall(r'^ok\s+', content, re.MULTILINE))
    fail_packages = len(re.findall(r'^FAIL\s+\S+', content, re.MULTILINE))
    result.raw_summary = f"{pass_count} passed, {fail_count} failed ({ok_packages} ok packages, {fail_packages} fail packages)"

    # If no individual tests found, look for package-level results
    if result.tests_total == 0:
        # Check for "PASS" or "FAIL" as standalone lines at end
        lines = content.strip().split('\n')
        last_meaningful = ""
        for line in reversed(lines):
            line = line.strip()
            if line in ("PASS", "FAIL") or line.startswith("ok ") or line.startswith("FAIL\t"):
                last_meaningful = line
                break

        if last_meaningful == "PASS" or last_meaningful.startswith("ok "):
            result.tests_passed = 1
            result.tests_total = 1
            result.parse_notes = "package-level pass only"
        elif last_meaningful == "FAIL" or last_meaningful.startswith("FAIL"):
            result.tests_failed = 1
            result.tests_total = 1
            result.parse_notes = "package-level fail only"

    return result


def parse_ginkgo_log(content: str) -> LogResult:
    """Parse Ginkgo (Go BDD) test output."""
    result = LogResult(framework="ginkgo", has_output=True, log_exists=True)

    # Look for "Ran X of Y Specs" pattern
    ran_match = re.search(r'Ran\s+(\d+)\s+of\s+(\d+)\s+Specs', content)
    if ran_match:
        result.tests_total = int(ran_match.group(1))

    # Look for SUCCESS/FAILURE line with counts
    # Pattern: SUCCESS! -- X Passed | Y Failed | Z Pending | W Skipped
    # (with ANSI codes stripped)
    clean = re.sub(r'\x1b\[[0-9;]*m', '', content)  # strip ANSI codes
    success_match = re.search(r'(\d+)\s+Passed\s*\|\s*(\d+)\s+Failed\s*\|\s*(\d+)\s+Pending\s*\|\s*(\d+)\s+Skipped', clean)
    if success_match:
        result.tests_passed = int(success_match.group(1))
        result.tests_failed = int(success_match.group(2))
        result.tests_skipped = int(success_match.group(4))
        result.tests_total = result.tests_passed + result.tests_failed
        result.raw_summary = f"{result.tests_passed} passed, {result.tests_failed} failed, {result.tests_skipped} skipped"
    elif ran_match:
        # If we have the Ran line but no summary, check for build failure
        if "[build failed]" in content or "[setup failed]" in content:
            result.has_build_failure = True
            result.tests_failed = result.tests_total if result.tests_total > 0 else 1
            result.tests_total = max(result.tests_total, 1)
            result.parse_notes = "build failure"

    return result


def parse_mocha_json_log(content: str) -> LogResult:
    """Parse Mocha JSON output (NodeBB)."""
    result = LogResult(framework="mocha-json", has_output=True, log_exists=True)

    # Find the JSON stats block embedded in log output
    # Try multiple patterns to locate the JSON start
    json_start = content.find('{\n  "stats"')
    if json_start == -1:
        json_start = content.find('{"stats"')
    if json_start == -1:
        # Try with different whitespace
        json_start = content.find('{\r\n  "stats"')

    if json_start >= 0:
        try:
            data = json.loads(content[json_start:])
            stats = data.get("stats", {})
            result.tests_total = stats.get("tests", 0)
            result.tests_passed = stats.get("passes", 0)
            result.tests_failed = stats.get("failures", 0)
            result.tests_skipped = stats.get("pending", 0)
            result.raw_summary = f"{result.tests_passed} passed, {result.tests_failed} failed out of {result.tests_total}"

            # Also extract which specific tests failed
            failures = data.get("failures", [])
            if failures:
                fail_titles = [f.get("title", "unknown") for f in failures]
                result.parse_notes = f"Failed: {'; '.join(fail_titles[:5])}"

            return result
        except json.JSONDecodeError:
            result.parse_notes = "JSON parse error in mocha output"
            return result

    result.parse_notes = "could not find mocha JSON stats block"
    return result


def parse_jest_log(content: str) -> LogResult:
    """Parse Jest test output (element-web, webclients)."""
    result = LogResult(framework="jest", has_output=True, log_exists=True)

    # Look for Jest summary: "Tests: X failed, Y passed, Z total"
    # There may be multiple runs in a single log; take the LAST one
    all_tests_matches = list(re.finditer(r'Tests:\s+(.*?)(?:\n|$)', content))
    if all_tests_matches:
        # Use the last Tests: line (final run result)
        summary = all_tests_matches[-1].group(1)
        failed = re.search(r'(\d+)\s+failed', summary)
        passed = re.search(r'(\d+)\s+passed', summary)
        skipped = re.search(r'(\d+)\s+skipped', summary)
        total = re.search(r'(\d+)\s+total', summary)

        if failed:
            result.tests_failed = int(failed.group(1))
        if passed:
            result.tests_passed = int(passed.group(1))
        if skipped:
            result.tests_skipped = int(skipped.group(1))
        if total:
            result.tests_total = int(total.group(1))
        else:
            result.tests_total = result.tests_passed + result.tests_failed
        result.raw_summary = summary.strip()
        return result

    # Count individual PASS/FAIL lines for test suites
    pass_suites = len(re.findall(r'^\s*PASS\s+', content, re.MULTILINE))
    fail_suites = len(re.findall(r'^\s*FAIL\s+', content, re.MULTILINE))

    if pass_suites + fail_suites > 0:
        result.tests_passed = pass_suites
        result.tests_failed = fail_suites
        result.tests_total = pass_suites + fail_suites
        result.raw_summary = f"{pass_suites} suite(s) passed, {fail_suites} suite(s) failed"
        result.framework = "jest-suites"
        return result

    # Check for build/compilation failures
    if "error TS" in content or "Module not found" in content or "Cannot find module" in content:
        result.has_build_failure = True
        result.parse_notes = "TypeScript/build error"
        return result

    # Check for test execution messages
    if "Test execution failed" in content:
        result.tests_failed = 1
        result.tests_total = 1
        result.parse_notes = "test execution failed"
    elif "Test execution completed" in content:
        result.parse_notes = "test execution completed (no counts)"

    return result


def parse_tutanota_log(content: str) -> LogResult:
    """Parse Tutanota test output (custom assertion-based framework)."""
    result = LogResult(framework="tutanota", has_output=True, log_exists=True)

    # Check for compilation errors first
    has_ts_error = "error TS" in content or "Error: Process failed" in content
    if has_ts_error:
        result.has_build_failure = True

    # Tutanota uses a custom assertion-based test framework with these patterns:
    # "All X assertions passed (old style total: Y)"
    # "N out of X assertions failed (old style total: Y). Bailed out Z time"
    all_passed = re.search(r'All\s+(\d+)\s+assertions?\s+passed', content)
    some_failed = re.search(r'(\d+)\s+out\s+of\s+(\d+)\s+assertions?\s+failed', content)

    if all_passed:
        result.tests_passed = int(all_passed.group(1))
        result.tests_total = result.tests_passed
        result.tests_failed = 0
        result.raw_summary = f"All {result.tests_passed} assertions passed"
        return result

    if some_failed:
        result.tests_failed = int(some_failed.group(1))
        result.tests_total = int(some_failed.group(2))
        result.tests_passed = result.tests_total - result.tests_failed
        result.raw_summary = f"{result.tests_failed} out of {result.tests_total} assertions failed"
        return result

    # If we have build errors but no assertion results
    if has_ts_error:
        result.tests_failed = 1
        result.tests_total = 1
        result.parse_notes = "TypeScript compilation error, no test results"
        return result

    # Check for "Selected tests completed" without assertion counts
    if "Selected tests completed" in content:
        result.parse_notes = "tests completed but no assertion counts found"
    else:
        result.parse_notes = "no test results found"

    return result


def parse_webclients_log(content: str) -> LogResult:
    """Parse webclients (Proton) test output - uses Jest."""
    return parse_jest_log(content)


def detect_framework(content: str, repo: str) -> str:
    """Detect the test framework based on log content and repo."""
    # Repo-based hints
    if repo in ("ansible", "qutebrowser", "openlibrary"):
        return "pytest"
    if repo in ("flipt", "vuls", "teleport"):
        return "go-test"
    if repo == "navidrome":
        return "go-test"  # ginkgo is detected inside parse_go_test_log
    if repo == "NodeBB":
        return "mocha-json"
    if repo in ("element-web", "webclients"):
        return "jest"
    if repo == "tutanota":
        return "tutanota"

    # Content-based detection
    if "test session starts" in content:
        return "pytest"
    if "=== RUN" in content or "--- PASS:" in content or "--- FAIL:" in content:
        return "go-test"
    if '"stats"' in content and '"passes"' in content:
        return "mocha-json"
    if "Test Suites:" in content or "Tests:" in content:
        return "jest"

    return "unknown"


def parse_log(content: str, repo: str) -> LogResult:
    """Parse a log file based on detected framework."""
    if not content or not content.strip():
        return LogResult(log_exists=True, has_output=False, parse_notes="empty log")

    framework = detect_framework(content, repo)

    if framework == "pytest":
        return parse_pytest_log(content)
    elif framework == "go-test":
        return parse_go_test_log(content)
    elif framework == "mocha-json":
        return parse_mocha_json_log(content)
    elif framework == "jest":
        return parse_jest_log(content)
    elif framework == "tutanota":
        return parse_tutanota_log(content)
    else:
        result = LogResult(framework="unknown", has_output=True, log_exists=True)
        result.parse_notes = "unknown framework"
        return result


def classify_task(task: TaskResult) -> str:
    """Classify a task based on pre-verification and verification results."""
    pre = task.pre_verification
    ver = task.verification

    # No verification log exists
    if not ver.log_exists:
        return "NO_VERIFICATION_LOG"

    # Neither log has meaningful output
    if not pre.has_output and not ver.has_output:
        return "NO_TEST_OUTPUT"

    # No tests ran in either phase (no passed, no failed, no errors)
    if pre.tests_total == 0 and ver.tests_total == 0:
        # Check for build failures
        if pre.has_build_failure and ver.has_build_failure:
            return "BUILD_FAILURE_BOTH"
        elif pre.has_build_failure and not ver.has_build_failure:
            return "BUILD_FIX_NO_TESTS"
        elif ver.has_build_failure:
            return "BUILD_FAILURE_POST"
        return "NO_TESTS_RAN"

    # Verification has results
    if ver.tests_total > 0:
        # Check if ALL verification tests were skipped (0 passed, 0 failed, all skipped)
        if ver.tests_passed == 0 and ver.tests_failed == 0 and ver.tests_errored == 0:
            if ver.tests_skipped > 0:
                return "ALL_TESTS_SKIPPED"
            # Has total but no pass/fail/error/skip - likely errored
            return "NOT_RESOLVED"

        if ver.tests_failed == 0 and ver.tests_errored == 0 and ver.tests_passed > 0:
            # All non-skipped verification tests pass
            if pre.tests_failed > 0 or pre.has_build_failure or pre.tests_errored > 0:
                return "RESOLVED"
            elif pre.tests_total == 0:
                # Pre-verification didn't produce test results (crash, build error, etc.)
                if pre.has_build_failure or "crash" in pre.parse_notes or "error" in pre.parse_notes:
                    return "RESOLVED"
                return "RESOLVED"
            elif pre.tests_failed == 0 and pre.tests_passed > 0 and pre.tests_errored == 0:
                # Tests also passed in pre-verification - tests were already passing
                return "TESTS_ALREADY_PASSING"
            else:
                return "RESOLVED"
        else:
            # Some verification tests failed or errored
            ver_issues = ver.tests_failed + ver.tests_errored
            pre_issues = pre.tests_failed + pre.tests_errored
            if pre_issues > 0:
                if ver_issues < pre_issues:
                    return "PARTIALLY_RESOLVED"
                elif ver_issues == pre_issues:
                    return "NOT_RESOLVED"
                else:
                    return "REGRESSION"
            return "NOT_RESOLVED"

    # Pre has results but verification doesn't
    if pre.tests_total > 0 and ver.tests_total == 0:
        if ver.has_build_failure:
            return "BUILD_FAILURE_POST"
        return "INDETERMINATE"

    return "INDETERMINATE"


def process_all_tasks() -> list[TaskResult]:
    """Process all task folders."""
    results = []

    for entry in sorted(os.listdir(BASE_DIR)):
        full_path = BASE_DIR / entry
        if not full_path.is_dir() or not entry.startswith(os.environ.get("MODEL_PREFIX", "claude-opus-4-6") + "-"):
            continue

        repo = detect_repo(entry)
        task_id = extract_task_id(entry, repo)

        task = TaskResult(
            folder_name=entry,
            repo=repo,
            task_id=task_id
        )

        # Read pre_verification.log
        pre_path = full_path / "pre_verification.log"
        if pre_path.exists():
            try:
                content = pre_path.read_text(encoding='utf-8', errors='replace')
                task.pre_verification = parse_log(content, repo)
            except Exception as e:
                task.pre_verification = LogResult(log_exists=True, parse_notes=f"read error: {e}")
        else:
            task.pre_verification = LogResult(log_exists=False, parse_notes="file missing")

        # Read verification.log
        ver_path = full_path / "verification.log"
        if ver_path.exists():
            try:
                content = ver_path.read_text(encoding='utf-8', errors='replace')
                task.verification = parse_log(content, repo)
            except Exception as e:
                task.verification = LogResult(log_exists=True, parse_notes=f"read error: {e}")
        else:
            task.verification = LogResult(log_exists=False, parse_notes="file missing")

        # Classify
        task.classification = classify_task(task)

        results.append(task)

    return results


def generate_report(results: list[TaskResult]) -> str:
    """Generate the audit report markdown."""
    lines = []

    # Header
    lines.append("# SWE-Bench Pro Evaluation Audit Report (Log-Based)")
    lines.append(f"Generated: 2026-02-23")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("This report is based **exclusively** on parsing the actual `pre_verification.log` and `verification.log` files")
    lines.append("in each task folder. It does NOT rely on `result.json` data, which has known issues.")
    lines.append("")
    lines.append("- **pre_verification.log**: Runs the fail-to-pass (F2P) test cases BEFORE the coding fix is applied.")
    lines.append("  These tests should FAIL, confirming the bug exists.")
    lines.append("- **verification.log**: Runs the F2P test cases AFTER the coding fix is applied.")
    lines.append("  These tests should PASS if the fix is correct.")
    lines.append("- **Pass-to-pass (P2P) tests**: Not evaluated (current workflow does not run them).")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- **Model**: {os.environ.get("MODEL_PREFIX", "claude-opus-4-6")}")
    lines.append("- **MCP**: Disabled (baseline)")
    lines.append("- **Repositories**: 11")
    lines.append(f"- **Total Tasks**: {len(results)}")

    resolved = sum(1 for r in results if r.classification == "RESOLVED")
    lines.append(f"- **Resolved (from logs)**: {resolved}/{len(results)} ({resolved*100/len(results):.1f}%)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Classification criteria
    lines.append("## Classification Criteria")
    lines.append("")
    lines.append("| Classification | Rule |")
    lines.append("|---|---|")
    lines.append("| **RESOLVED** | Pre-verification shows failures (or build error); verification shows all tests passing |")
    lines.append("| **NOT_RESOLVED** | Verification shows test failures |")
    lines.append("| **PARTIALLY_RESOLVED** | Verification has fewer failures than pre-verification, but some remain |")
    lines.append("| **TESTS_ALREADY_PASSING** | Tests passed in both pre-verification and verification (F2P tests didn't fail before fix) |")
    lines.append("| **REGRESSION** | Verification has more failures than pre-verification |")
    lines.append("| **NO_VERIFICATION_LOG** | verification.log file is missing |")
    lines.append("| **NO_TESTS_RAN** | Neither pre nor post verification produced test results |")
    lines.append("| **NO_TEST_OUTPUT** | Log files exist but contain no meaningful output |")
    lines.append("| **BUILD_FAILURE_BOTH** | Build failed in both phases |")
    lines.append("| **BUILD_FIX_NO_TESTS** | Build failure fixed but no test counts available |")
    lines.append("| **BUILD_FAILURE_POST** | Build failed in post-verification |")
    lines.append("| **ALL_TESTS_SKIPPED** | Verification ran but all tests were skipped (0 pass, 0 fail) |")
    lines.append("| **INDETERMINATE** | Cannot determine status from logs |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Full results table
    lines.append("## Complete Task-Level Results")
    lines.append("")
    lines.append("| # | Repo | Task ID | Framework | Pre: Total | Pre: Pass | Pre: Fail | Pre: Build Err | Ver: Total | Ver: Pass | Ver: Fail | Ver: Build Err | Classification |")
    lines.append("|--:|------|---------|-----------|----------:|---------:|---------:|:--------------:|----------:|---------:|---------:|:--------------:|----------------|")

    for i, task in enumerate(results, 1):
        pre = task.pre_verification
        ver = task.verification
        pre_build = "Yes" if pre.has_build_failure else ""
        ver_build = "Yes" if ver.has_build_failure else ""
        ver_exists = "" if ver.log_exists else "N/A"

        if not ver.log_exists:
            lines.append(f"| {i} | {task.repo} | {task.task_id} | {pre.framework} | {pre.tests_total} | {pre.tests_passed} | {pre.tests_failed} | {pre_build} | N/A | N/A | N/A | N/A | {task.classification} |")
        else:
            lines.append(f"| {i} | {task.repo} | {task.task_id} | {ver.framework} | {pre.tests_total} | {pre.tests_passed} | {pre.tests_failed} | {pre_build} | {ver.tests_total} | {ver.tests_passed} | {ver.tests_failed} | {ver_build} | {task.classification} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Classification summary
    lines.append("## Classification Summary")
    lines.append("")
    from collections import Counter
    class_counts = Counter(r.classification for r in results)
    lines.append("| Classification | Count | % of Total |")
    lines.append("|---|---:|---:|")
    for cls in ["RESOLVED", "NOT_RESOLVED", "PARTIALLY_RESOLVED", "TESTS_ALREADY_PASSING",
                "REGRESSION", "ALL_TESTS_SKIPPED", "NO_VERIFICATION_LOG", "NO_TESTS_RAN", "NO_TEST_OUTPUT",
                "BUILD_FAILURE_BOTH", "BUILD_FIX_NO_TESTS", "BUILD_FAILURE_POST", "INDETERMINATE"]:
        count = class_counts.get(cls, 0)
        if count > 0:
            lines.append(f"| {cls} | {count} | {count*100/len(results):.1f}% |")
    lines.append(f"| **Total** | **{len(results)}** | **100%** |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-repository summary
    lines.append("## Per-Repository Summary")
    lines.append("")
    lines.append("| Repo | Tasks | Resolved | Not Resolved | Partial | Tests Already Passing | No Verification | No Tests | Other |")
    lines.append("|------|------:|---------:|-------------:|--------:|----------------------:|----------------:|---------:|------:|")

    repos = sorted(set(r.repo for r in results))
    for repo in repos:
        repo_tasks = [r for r in results if r.repo == repo]
        count = len(repo_tasks)
        res = sum(1 for r in repo_tasks if r.classification == "RESOLVED")
        not_res = sum(1 for r in repo_tasks if r.classification == "NOT_RESOLVED")
        partial = sum(1 for r in repo_tasks if r.classification == "PARTIALLY_RESOLVED")
        already = sum(1 for r in repo_tasks if r.classification == "TESTS_ALREADY_PASSING")
        no_ver = sum(1 for r in repo_tasks if r.classification == "NO_VERIFICATION_LOG")
        no_tests = sum(1 for r in repo_tasks if r.classification in ("NO_TESTS_RAN", "NO_TEST_OUTPUT", "BUILD_FAILURE_BOTH", "BUILD_FIX_NO_TESTS", "BUILD_FAILURE_POST", "ALL_TESTS_SKIPPED"))
        other = count - res - not_res - partial - already - no_ver - no_tests
        lines.append(f"| {repo} | {count} | {res} | {not_res} | {partial} | {already} | {no_ver} | {no_tests} | {other} |")

    total_res = sum(1 for r in results if r.classification == "RESOLVED")
    total_not = sum(1 for r in results if r.classification == "NOT_RESOLVED")
    total_partial = sum(1 for r in results if r.classification == "PARTIALLY_RESOLVED")
    total_already = sum(1 for r in results if r.classification == "TESTS_ALREADY_PASSING")
    total_nover = sum(1 for r in results if r.classification == "NO_VERIFICATION_LOG")
    total_notests = sum(1 for r in results if r.classification in ("NO_TESTS_RAN", "NO_TEST_OUTPUT", "BUILD_FAILURE_BOTH", "BUILD_FIX_NO_TESTS", "BUILD_FAILURE_POST", "ALL_TESTS_SKIPPED"))
    total_other = len(results) - total_res - total_not - total_partial - total_already - total_nover - total_notests
    lines.append(f"| **Total** | **{len(results)}** | **{total_res}** | **{total_not}** | **{total_partial}** | **{total_already}** | **{total_nover}** | **{total_notests}** | **{total_other}** |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Detailed breakdown of non-resolved tasks
    non_resolved = [r for r in results if r.classification != "RESOLVED"]
    if non_resolved:
        lines.append("## Non-Resolved Task Details")
        lines.append("")

        for cls in ["NOT_RESOLVED", "PARTIALLY_RESOLVED", "TESTS_ALREADY_PASSING",
                    "ALL_TESTS_SKIPPED", "NO_VERIFICATION_LOG", "NO_TESTS_RAN", "NO_TEST_OUTPUT",
                    "BUILD_FAILURE_BOTH", "BUILD_FIX_NO_TESTS", "BUILD_FAILURE_POST",
                    "REGRESSION", "INDETERMINATE"]:
            cls_tasks = [r for r in results if r.classification == cls]
            if cls_tasks:
                lines.append(f"### {cls} ({len(cls_tasks)} tasks)")
                lines.append("")
                lines.append("| Task ID | Repo | Pre Notes | Ver Notes |")
                lines.append("|---------|------|-----------|-----------|")
                for t in cls_tasks:
                    pre_notes = t.pre_verification.parse_notes or f"total={t.pre_verification.tests_total} pass={t.pre_verification.tests_passed} fail={t.pre_verification.tests_failed}"
                    ver_notes = t.verification.parse_notes or f"total={t.verification.tests_total} pass={t.verification.tests_passed} fail={t.verification.tests_failed}"
                    if not t.verification.log_exists:
                        ver_notes = "FILE MISSING"
                    lines.append(f"| {t.task_id} | {t.repo} | {pre_notes} | {ver_notes} |")
                lines.append("")

    # Score comparison
    lines.append("---")
    lines.append("")
    lines.append("## Score Analysis")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Tasks with verification evidence | {sum(1 for r in results if r.verification.tests_total > 0 or r.verification.log_exists)} |")
    lines.append(f"| **Resolved (log-based)** | **{resolved}/{len(results)} = {resolved*100/len(results):.1f}%** |")

    verifiable = sum(1 for r in results if r.classification not in ("NO_VERIFICATION_LOG", "NO_TESTS_RAN", "NO_TEST_OUTPUT", "BUILD_FAILURE_BOTH", "BUILD_FIX_NO_TESTS", "BUILD_FAILURE_POST", "ALL_TESTS_SKIPPED", "INDETERMINATE"))
    lines.append(f"| Verifiable tasks (tests actually ran) | {verifiable} |")
    if verifiable > 0:
        lines.append(f"| Resolved among verifiable | {resolved}/{verifiable} = {resolved*100/verifiable:.1f}% |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Report generated: 2026-02-23*")
    lines.append(f"*Source: pre_verification.log and verification.log files*")
    lines.append(f"*Does NOT rely on result.json*")

    return "\n".join(lines)


if __name__ == "__main__":
    print("Parsing all task folders...", file=sys.stderr)
    results = process_all_tasks()
    print(f"Processed {len(results)} tasks", file=sys.stderr)

    # Print per-task summary to stderr for debugging
    for r in results:
        pre = r.pre_verification
        ver = r.verification
        print(f"  {r.task_id}: pre({pre.framework}: {pre.tests_total}t/{pre.tests_passed}p/{pre.tests_failed}f) "
              f"ver({ver.framework}: {ver.tests_total}t/{ver.tests_passed}p/{ver.tests_failed}f) "
              f"=> {r.classification}", file=sys.stderr)

    report = generate_report(results)

    # Write report
    output_path = BASE_DIR / "evaluation_audit_report_logbased.md"
    output_path.write_text(report)
    print(f"\nReport written to: {output_path}", file=sys.stderr)

    # Also print to stdout
    print(report)
