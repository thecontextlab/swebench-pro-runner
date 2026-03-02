#!/usr/bin/env python3
"""Deep audit of SWE-bench Pro evaluation artifacts via task YAML cross-referencing.

Cross-references:
  1. Task YAML fail_to_pass list (source of truth for which tests must pass)
  2. verification.log (actual test execution output)
  3. result.json (only for task_id and the claimed resolved status)

This avoids relying on result.json's broken test counts and resolved status,
instead determining ground truth from the verification.log directly.
"""

import argparse
import csv
import json
import os
import re
import sys

# Add parent directory for _utils import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _utils import (
    REPOS, get_repo_from_task_id, get_framework_for_repo,
    load_task_yaml, load_result, get_task_id,
)

# ---------------------------------------------------------------------------
# Per-framework verification.log parsers
# ---------------------------------------------------------------------------

def _strip_ansi(text):
    """Remove ANSI escape codes from text."""
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def parse_pytest(fail_to_pass, vlog_text):
    """Parse pytest verification.log output.

    Pytest output format (sometimes PASSED/FAILED is on same line, sometimes next):
      test/path/file.py::TestClass::test_name PASSED
      test/path/file.py::TestClass::test_name [output...]\nPASSED
      test/path/file.py::TestClass::test_name FAILED
      test/path/file.py::TestClass::test_name XFAIL
      test/path/file.py::TestClass::test_name XPASS
    Also handles early stopping with -x flag.

    XFAIL (expected failure) and XPASS (unexpected pass) are both treated as
    passing states for regression purposes — they mean the test behaved as
    expected or better.
    """
    outcomes = {}
    lines = vlog_text.splitlines()

    # States that count as "passed" for regression/audit purposes
    _PASS_STATES = (" PASSED", " XFAIL", " XPASS")
    _FAIL_STATES = (" FAILED", " ERROR")

    def _check_line(line):
        """Return 'PASSED', 'FAILED', or None based on line content."""
        for state in _PASS_STATES:
            if state in line:
                return "PASSED"
        for state in _FAIL_STATES:
            if state in line:
                return "FAILED"
        # Also catch "ERROR" at the very start of a line (no leading space)
        stripped = line.lstrip()
        if stripped.startswith("ERROR ") or stripped == "ERROR":
            return "FAILED"
        return None

    for ftp_test in fail_to_pass:
        found = False
        # Search for lines containing the test ID
        for i, line in enumerate(lines):
            if ftp_test in line:
                # Check same line for result
                result = _check_line(line)
                if result:
                    outcomes[ftp_test] = result
                    found = True
                    break
                else:
                    # PASSED/FAILED may be on a subsequent line (pytest -v with stdout)
                    # Look ahead up to 10 lines for the result
                    for j in range(i + 1, min(i + 11, len(lines))):
                        ahead = lines[j].strip()
                        if ahead in ("PASSED", "XFAIL", "XPASS") or \
                           ahead.startswith("PASSED ") or \
                           ahead.startswith("XFAIL ") or \
                           ahead.startswith("XPASS "):
                            outcomes[ftp_test] = "PASSED"
                            found = True
                            break
                        elif ahead == "FAILED" or ahead.startswith("FAILED "):
                            outcomes[ftp_test] = "FAILED"
                            found = True
                            break
                        # If we hit the next test ID, stop looking
                        if "::" in ahead and (
                            _check_line(ahead) is not None or
                            ahead.startswith("test/") or ahead.startswith("tests/")
                        ):
                            break
                    if found:
                        break

        if not found:
            # Check the short test summary info section for FAILED lines
            for line in lines:
                if line.startswith("FAILED ") and ftp_test in line:
                    outcomes[ftp_test] = "FAILED"
                    found = True
                    break
        if not found:
            outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


def _detect_go_build_failures(text):
    """Detect Go packages that failed to build.

    Go test output for build failures:
      FAIL    package/path [build failed]
      FAIL    package/path [setup failed]

    Returns a set of failed package paths.
    """
    failed_pkgs = set()
    for m in re.finditer(r'^FAIL\s+(\S+)\s+\[build failed\]', text, re.MULTILINE):
        failed_pkgs.add(m.group(1))
    for m in re.finditer(r'^FAIL\s+(\S+)\s+\[setup failed\]', text, re.MULTILINE):
        failed_pkgs.add(m.group(1))
    return failed_pkgs


def parse_go(fail_to_pass, vlog_text):
    """Parse Go test verification.log output.

    Go test output format:
      === RUN   TestFunctionName
      --- PASS: TestFunctionName (0.00s)
      --- FAIL: TestFunctionName (0.05s)
    For subtests:
      === RUN   TestName/SubTest
          --- PASS: TestName/SubTest (0.00s)

    Also detects build failures in packages — when `go test ./...` fails to
    build a package, tests in that package never execute. These are reported
    as BUILD_FAIL rather than NOT_FOUND.
    """
    outcomes = {}
    text = _strip_ansi(vlog_text)
    build_failed_pkgs = _detect_go_build_failures(text)

    for ftp_test in fail_to_pass:
        # Match "--- PASS: TestName" or "--- FAIL: TestName"
        escaped = re.escape(ftp_test)
        pattern = r'---\s+(PASS|FAIL):\s+' + escaped + r'[\s(/]'
        match = re.search(pattern, text)
        if match:
            result = match.group(1)
            outcomes[ftp_test] = "PASSED" if result == "PASS" else "FAILED"
        else:
            # Try looser match: test name at end of line
            pattern2 = r'---\s+(PASS|FAIL):\s+' + escaped + r'\s*$'
            match2 = re.search(pattern2, text, re.MULTILINE)
            if match2:
                result = match2.group(1)
                outcomes[ftp_test] = "PASSED" if result == "PASS" else "FAILED"
            elif build_failed_pkgs:
                # Test not found and there are build failures — likely in a
                # package that failed to build
                outcomes[ftp_test] = "BUILD_FAIL"
            else:
                outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


def parse_go_custom(fail_to_pass, vlog_text):
    """Parse Teleport's custom Go test runner verification.log.

    Teleport's run_script.sh:
      - Greps for test function existence
      - Runs each test individually
      - "Running fail_to_pass test: TestName"
      - "Test function exists, attempting to run..."
      - "EXPECTED: Test function TestName does not exist yet"
      - "--- PASS: TestName (Xs)" or "--- FAIL: TestName"

    Also detects build failures (same as parse_go) for cases where
    the test package fails to compile.
    """
    outcomes = {}
    text = _strip_ansi(vlog_text)
    build_failed_pkgs = _detect_go_build_failures(text)

    for ftp_test in fail_to_pass:
        escaped = re.escape(ftp_test)

        # Check for "Test function does not exist"
        not_exist_pattern = r'EXPECTED: Test function ' + escaped + r' does not exist'
        if re.search(not_exist_pattern, text):
            outcomes[ftp_test] = "NOT_EXIST"
            continue

        # Check for --- PASS/FAIL
        pattern = r'---\s+(PASS|FAIL):\s+' + escaped + r'[\s(]'
        match = re.search(pattern, text)
        if match:
            result = match.group(1)
            outcomes[ftp_test] = "PASSED" if result == "PASS" else "FAILED"
        else:
            # Looser match
            pattern2 = r'---\s+(PASS|FAIL):\s+' + escaped + r'\s*$'
            match2 = re.search(pattern2, text, re.MULTILINE)
            if match2:
                result = match2.group(1)
                outcomes[ftp_test] = "PASSED" if result == "PASS" else "FAILED"
            elif build_failed_pkgs:
                outcomes[ftp_test] = "BUILD_FAIL"
            else:
                outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


def parse_jest(fail_to_pass, vlog_text):
    """Parse Jest verification.log output (element-web).

    fail_to_pass format: "test/file.tsx | Suite Name | test description"
    verification.log:
      PASS test/file.tsx
        Suite Name
          ✓ test description (Xms)
          ✕ test description (Xms)
    """
    outcomes = {}

    for ftp_test in fail_to_pass:
        parts = [p.strip() for p in ftp_test.split(" | ")]
        file_path = parts[0] if parts else ""
        test_desc = parts[-1] if len(parts) > 1 else None

        if not test_desc:
            # Can't match without a test description, check file-level
            if re.search(r'^PASS\s+' + re.escape(file_path), vlog_text, re.MULTILINE):
                outcomes[ftp_test] = "PASSED"
            elif re.search(r'^FAIL\s+' + re.escape(file_path), vlog_text, re.MULTILINE):
                outcomes[ftp_test] = "FAILED"
            else:
                outcomes[ftp_test] = "NOT_FOUND"
            continue

        # Check file-level first
        file_passed = bool(re.search(
            r'^PASS\s+' + re.escape(file_path), vlog_text, re.MULTILINE
        ))
        file_failed = bool(re.search(
            r'^FAIL\s+' + re.escape(file_path), vlog_text, re.MULTILINE
        ))

        if not file_passed and not file_failed:
            outcomes[ftp_test] = "NOT_FOUND"
            continue

        # Check individual test by description
        # ✓ or ✕ followed by test description
        escaped_desc = re.escape(test_desc)
        pass_match = re.search(r'[✓✓]\s+' + escaped_desc, vlog_text)
        fail_match = re.search(r'[✕✗×]\s+' + escaped_desc, vlog_text)

        if pass_match and not fail_match:
            outcomes[ftp_test] = "PASSED"
        elif fail_match:
            outcomes[ftp_test] = "FAILED"
        elif file_passed:
            # File passed overall but couldn't find specific test line —
            # if the file PASS'd and the test name wasn't explicitly failed, assume passed
            outcomes[ftp_test] = "PASSED"
        else:
            outcomes[ftp_test] = "FAILED"

    return outcomes


def parse_jest_workspace(fail_to_pass, vlog_text):
    """Parse Jest workspace (webclients) verification.log.

    fail_to_pass format: "@proton/pkg:file.tsx | test desc"
    verification.log sections:
      Running test: @proton/pkg:file.tsx | test desc
      Running in @proton/pkg: file.tsx | test desc
      ...Jest output...
      Test execution completed for @proton/pkg:file.tsx | test desc
      OR
      Test execution failed for @proton/pkg:file.tsx | test desc
    """
    outcomes = {}

    for ftp_test in fail_to_pass:
        escaped = re.escape(ftp_test)

        # Check for explicit completion/failure messages
        completed = re.search(
            r'Test execution completed for\s+' + escaped, vlog_text
        )
        failed_msg = re.search(
            r'Test execution failed for\s+' + escaped, vlog_text
        )

        if completed and not failed_msg:
            outcomes[ftp_test] = "PASSED"
            continue
        if failed_msg:
            # Also check for ✓/✕ and PASS/FAIL within the test section
            # Find the section for this test
            section_start = re.search(
                r'Running test:\s+' + escaped, vlog_text
            )
            if section_start:
                section_text = vlog_text[section_start.start():]
                # Find next "Running test:" or end
                next_test = re.search(r'\nRunning test:', section_text[1:])
                if next_test:
                    section_text = section_text[:next_test.start() + 1]

                # Check Jest output within section
                if re.search(r'^PASS\s', section_text, re.MULTILINE):
                    outcomes[ftp_test] = "PASSED"
                    continue

            outcomes[ftp_test] = "FAILED"
            continue

        # Check if test was even attempted
        running = re.search(r'Running test:\s+' + escaped, vlog_text)
        if not running:
            outcomes[ftp_test] = "NOT_FOUND"
            continue

        # Test was started but no completion message — check Jest output
        section_start = running.start()
        section_text = vlog_text[section_start:]
        next_test = re.search(r'\nRunning test:', section_text[1:])
        if next_test:
            section_text = section_text[:next_test.start() + 1]

        # Look for Jest PASS/FAIL at file level
        if re.search(r'^PASS\s', section_text, re.MULTILINE):
            outcomes[ftp_test] = "PASSED"
        elif re.search(r'^FAIL\s', section_text, re.MULTILINE):
            outcomes[ftp_test] = "FAILED"
        else:
            # Check test count: "Tests: X skipped, X total" with 0 ran
            skip_match = re.search(
                r'Tests:\s+(\d+)\s+skipped,\s+(\d+)\s+total', section_text
            )
            if skip_match and skip_match.group(1) == skip_match.group(2):
                # All tests skipped — test name pattern didn't match
                outcomes[ftp_test] = "NOT_FOUND"
            else:
                outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


def parse_mocha(fail_to_pass, vlog_text):
    """Parse Mocha (NodeBB) verification.log output.

    NodeBB outputs JSON with stats and test arrays.
    fail_to_pass format: "test/file.js | Suite Name | test description"
    JSON fullTitle format: "test/file.js::Suite Name test/file.js::SubSuite ... title"
    """
    outcomes = {}

    # Try to extract JSON from the verification log
    json_data = _extract_mocha_json(vlog_text)

    if json_data:
        stats = json_data.get("stats", {})
        tests = json_data.get("tests", [])
        failures = json_data.get("failures", [])
        passes = json_data.get("passes", [])

        # If tests array is empty but there are failures (e.g. "before all"
        # hook failures), all tests effectively failed
        if not tests and failures:
            for ftp_test in fail_to_pass:
                outcomes[ftp_test] = "FAILED"
            return outcomes

        for ftp_test in fail_to_pass:
            parts = [p.strip() for p in ftp_test.split(" | ")]
            # YAML format: "file | Suite hierarchy test_title"
            # JSON title: just "test_title" (short)
            # JSON fullTitle: "file::Suite file::SubSuite ... test_title"
            # Strategy: extract the suite+title from after the | and match against
            # JSON tests by checking if the JSON title is a suffix of yaml_desc
            yaml_desc = parts[-1] if len(parts) > 1 else ftp_test

            found = False
            # First try exact match on fullTitle or title
            for t in tests:
                title = t.get("title", "").strip()
                ft = t.get("fullTitle", "").strip()

                # Strip trailing whitespace from yaml_desc too for comparison
                yaml_desc_stripped = yaml_desc.strip()

                # Check if yaml_desc ends with the JSON test title
                if title and (yaml_desc_stripped.endswith(title) or
                              yaml_desc.endswith(title)):
                    err = t.get("err", {})
                    if not err or err == {}:
                        outcomes[ftp_test] = "PASSED"
                    else:
                        outcomes[ftp_test] = "FAILED"
                    found = True
                    break
                # Also check if yaml_desc is contained in fullTitle
                if yaml_desc_stripped in ft or yaml_desc in ft:
                    err = t.get("err", {})
                    if not err or err == {}:
                        outcomes[ftp_test] = "PASSED"
                    else:
                        outcomes[ftp_test] = "FAILED"
                    found = True
                    break

            if not found:
                outcomes[ftp_test] = "NOT_FOUND"
    else:
        # No JSON found — try text-based parsing
        for ftp_test in fail_to_pass:
            parts = [p.strip() for p in ftp_test.split(" | ")]
            test_title = parts[-1] if parts else ftp_test
            escaped = re.escape(test_title)
            if re.search(r'[✓✔]\s+' + escaped, vlog_text):
                outcomes[ftp_test] = "PASSED"
            elif re.search(r'[✗✕]\s+' + escaped, vlog_text):
                outcomes[ftp_test] = "FAILED"
            elif re.search(r'\d+\)\s+' + escaped, vlog_text):
                # Mocha numbered failures: "1) test title"
                outcomes[ftp_test] = "FAILED"
            else:
                outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


def _extract_mocha_json(text):
    """Extract the JSON object from NodeBB verification.log.

    The JSON starts after server logs and contains stats, tests, passes, failures.
    """
    # Find the first '{' that starts the JSON block
    # It typically appears after "info:" log lines
    brace_depth = 0
    json_start = None
    json_end = None

    for i, ch in enumerate(text):
        if ch == '{' and json_start is None:
            # Verify this looks like the mocha JSON (has "stats" key nearby)
            lookahead = text[i:i + 50]
            if '"stats"' in lookahead:
                json_start = i
                brace_depth = 1
                continue
        if json_start is not None:
            if ch == '{':
                brace_depth += 1
            elif ch == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    json_end = i + 1
                    break

    if json_start is not None and json_end is not None:
        try:
            return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            return None
    return None


def parse_custom_tutanota(fail_to_pass, vlog_text):
    """Parse Tutanota's custom test runner verification.log.

    fail_to_pass format: "test/path/TestFile.js | test suite"
    verification.log ends with:
      "All X assertions passed (old style total: Y)"
      OR
      "X out of Y assertions failed"
    Individual test suites are all-or-nothing in Tutanota's runner.
    """
    outcomes = {}

    # Check the summary line
    all_passed = re.search(
        r'All\s+\d+\s+assertions?\s+passed', vlog_text
    )
    some_failed = re.search(
        r'(\d+)\s+out of\s+(\d+)\s+assertions?\s+failed', vlog_text
    )

    if all_passed and not some_failed:
        # All assertions passed — all fail_to_pass tests are PASSED
        for ftp_test in fail_to_pass:
            outcomes[ftp_test] = "PASSED"
    elif some_failed:
        # Some failed — we can't tell which specific test suites failed
        # from the summary alone, so mark all as INDETERMINATE
        # unless we can find per-suite info
        for ftp_test in fail_to_pass:
            outcomes[ftp_test] = "FAILED"
    else:
        # No summary found — check for build failures or other errors
        if "Build failed" in vlog_text or "Error:" in vlog_text:
            for ftp_test in fail_to_pass:
                outcomes[ftp_test] = "FAILED"
        else:
            for ftp_test in fail_to_pass:
                outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


# ---------------------------------------------------------------------------
# Framework dispatcher
# ---------------------------------------------------------------------------

FRAMEWORK_PARSERS = {
    "pytest": parse_pytest,
    "go": parse_go,
    "go_custom": parse_go_custom,
    "jest": parse_jest,
    "jest_workspace": parse_jest_workspace,
    "mocha": parse_mocha,
    "custom": parse_custom_tutanota,
}


def parse_verification_log(framework, fail_to_pass, vlog_text):
    """Dispatch to the appropriate parser based on framework."""
    parser = FRAMEWORK_PARSERS.get(framework)
    if parser:
        return parser(fail_to_pass, vlog_text)
    return {t: "NOT_FOUND" for t in fail_to_pass}


# ---------------------------------------------------------------------------
# Crash / false-negative detection
# ---------------------------------------------------------------------------

def detect_post_test_crash(vlog_text, framework):
    """Detect post-test crashes that cause non-zero exit despite all tests passing.

    Returns a string describing the crash, or None.
    """
    # Qutebrowser X11 crash
    if "XIO:  fatal IO error" in vlog_text:
        # Check if this appears AFTER the pytest summary
        summary_match = re.search(r'=+ \d+ passed', vlog_text)
        xio_match = re.search(r'XIO:\s+fatal IO error', vlog_text)
        if summary_match and xio_match and xio_match.start() > summary_match.start():
            return "X11_CRASH"

    # Jest infinite timer recursion
    if "Ran 100000 timers" in vlog_text and "infinite recursion" in vlog_text:
        return "JEST_INFINITE_TIMER"

    # Jest: unrelated test suites failed (the target tests passed but other tests fail)
    if framework in ("jest", "jest_workspace"):
        # Check for "Test Suites: X failed" in the summary
        suite_fail = re.search(
            r'Test Suites:\s+(\d+)\s+failed', vlog_text
        )
        if suite_fail:
            return "JEST_OTHER_FAILURE"

        # Node.js crash at end
        if re.search(r'Node\.js v\d+', vlog_text.split('\n')[-1] if vlog_text.strip() else ""):
            return "JEST_NODE_CRASH"

    return None


def detect_early_stop(vlog_text, framework):
    """Detect pytest -x early stopping."""
    if framework == "pytest":
        if "stopping after" in vlog_text and "failures" in vlog_text:
            return True
    return False


# ---------------------------------------------------------------------------
# Main audit logic
# ---------------------------------------------------------------------------

def audit_single_artifact(folder_path, task_yaml_dir):
    """Audit a single artifact folder.

    Returns a dict with audit results, or None if the folder can't be audited.
    """
    result_data = load_result(folder_path)
    if not result_data:
        return None

    task_id = get_task_id(result_data)
    if not task_id:
        return None

    repo = get_repo_from_task_id(task_id)
    if not repo:
        return {"task_id": task_id, "error": f"Unknown org in task_id: {task_id}"}

    framework = get_framework_for_repo(repo)

    # Load fail_to_pass from task YAML
    fail_to_pass = load_task_yaml(task_yaml_dir, task_id)
    if fail_to_pass is None:
        return {
            "task_id": task_id, "repo": repo, "framework": framework,
            "error": "YAML not found",
            "rj_resolved": result_data.get("resolved", False),
        }

    if not fail_to_pass:
        return {
            "task_id": task_id, "repo": repo, "framework": framework,
            "error": "Empty fail_to_pass list",
            "rj_resolved": result_data.get("resolved", False),
        }

    rj_resolved = result_data.get("resolved", False)

    # Load verification.log
    vlog_path = os.path.join(folder_path, "verification.log")
    if not os.path.exists(vlog_path):
        return {
            "task_id": task_id, "repo": repo, "framework": framework,
            "rj_resolved": rj_resolved, "true_resolved": False,
            "category": "TRUE-NEGATIVE" if not rj_resolved else "FALSE-POSITIVE",
            "ftp_count": len(fail_to_pass), "ftp_passed": 0, "ftp_failed": 0,
            "ftp_not_found": len(fail_to_pass), "ftp_not_exist": 0,
            "early_stop": False, "crash_type": None,
            "detail": "no verification.log (agent failed before tests ran)",
            "subcategory": None,
            "passed_tests": [], "failed_tests": [], "not_found_tests": fail_to_pass,
            "not_exist_tests": [], "verification_exit_code": result_data.get("verification_exit_code"),
        }

    try:
        with open(vlog_path, errors="replace") as f:
            vlog_text = f.read()
    except OSError:
        return {
            "task_id": task_id, "repo": repo, "framework": framework,
            "rj_resolved": rj_resolved, "true_resolved": False,
            "category": "TRUE-NEGATIVE" if not rj_resolved else "FALSE-POSITIVE",
            "ftp_count": len(fail_to_pass), "ftp_passed": 0, "ftp_failed": 0,
            "ftp_not_found": len(fail_to_pass), "ftp_not_exist": 0,
            "early_stop": False, "crash_type": None,
            "detail": "cannot read verification.log",
            "subcategory": None,
            "passed_tests": [], "failed_tests": [], "not_found_tests": fail_to_pass,
            "not_exist_tests": [], "verification_exit_code": result_data.get("verification_exit_code"),
        }

    # Parse verification.log
    test_outcomes = parse_verification_log(framework, fail_to_pass, vlog_text)

    # Classify outcomes
    passed = [t for t, o in test_outcomes.items() if o == "PASSED"]
    failed = [t for t, o in test_outcomes.items() if o == "FAILED"]
    not_found = [t for t, o in test_outcomes.items() if o == "NOT_FOUND"]
    not_exist = [t for t, o in test_outcomes.items() if o == "NOT_EXIST"]
    build_fail = [t for t, o in test_outcomes.items() if o == "BUILD_FAIL"]

    # Determine true_resolved — BUILD_FAIL tests are treated like NOT_FOUND
    true_resolved = (len(failed) == 0 and len(not_found) == 0
                     and len(not_exist) == 0 and len(build_fail) == 0)

    # Categorize
    if true_resolved and rj_resolved:
        category = "TRUE-POSITIVE"
    elif not true_resolved and not rj_resolved:
        category = "TRUE-NEGATIVE"
    elif true_resolved and not rj_resolved:
        category = "FALSE-NEGATIVE"
    else:
        category = "FALSE-POSITIVE"

    # Sub-categorize
    subcategory = None
    crash_type = detect_post_test_crash(vlog_text, framework)
    early_stop = detect_early_stop(vlog_text, framework)

    if category == "FALSE-NEGATIVE":
        if crash_type == "X11_CRASH":
            subcategory = "FN-CRASH-X11"
        elif crash_type == "JEST_INFINITE_TIMER":
            subcategory = "FN-JEST-TIMER"
        elif crash_type == "JEST_OTHER_FAILURE":
            subcategory = "FN-JEST-OTHER"
        elif crash_type == "JEST_NODE_CRASH":
            subcategory = "FN-JEST-CRASH"
        elif not_exist:
            subcategory = "FN-SCRIPT-BUG"
        else:
            subcategory = "FN-UNKNOWN"
    elif category == "FALSE-POSITIVE":
        if framework in ("jest", "jest_workspace"):
            subcategory = "FP-JEST-EXIT0"
        else:
            subcategory = "FP-UNKNOWN"

    # Build detail string
    detail_parts = []
    if passed:
        detail_parts.append(f"{len(passed)} passed")
    if failed:
        detail_parts.append(f"{len(failed)} failed")
    if not_found:
        detail_parts.append(f"{len(not_found)} not found")
    if not_exist:
        detail_parts.append(f"{len(not_exist)} not exist")
    if build_fail:
        detail_parts.append(f"{len(build_fail)} build fail")
    if early_stop:
        detail_parts.append("early-stop")
    if crash_type:
        detail_parts.append(crash_type)
    detail = ", ".join(detail_parts)

    return {
        "task_id": task_id,
        "repo": repo,
        "framework": framework,
        "rj_resolved": rj_resolved,
        "true_resolved": true_resolved,
        "category": category,
        "subcategory": subcategory,
        "ftp_count": len(fail_to_pass),
        "ftp_passed": len(passed),
        "ftp_failed": len(failed),
        "ftp_not_found": len(not_found),
        "ftp_not_exist": len(not_exist),
        "ftp_build_fail": len(build_fail),
        "early_stop": early_stop,
        "crash_type": crash_type,
        "detail": detail,
        "passed_tests": passed,
        "failed_tests": failed,
        "not_found_tests": not_found,
        "not_exist_tests": not_exist,
        "build_fail_tests": build_fail,
        "verification_exit_code": result_data.get("verification_exit_code"),
    }


def audit_artifact_dir(artifact_dir, task_yaml_dir, label=None):
    """Audit all artifact folders in a directory."""
    results = []
    errors = []

    if not os.path.exists(artifact_dir):
        print(f"ERROR: Artifact directory not found: {artifact_dir}")
        return results, errors

    folders = sorted([
        d for d in os.listdir(artifact_dir)
        if os.path.isdir(os.path.join(artifact_dir, d))
    ])

    for folder in folders:
        folder_path = os.path.join(artifact_dir, folder)
        result = audit_single_artifact(folder_path, task_yaml_dir)
        if result is None:
            continue
        if "error" in result:
            errors.append(result)
        else:
            results.append(result)

    return results, errors


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def _short_task(task_id, max_len=20):
    """Shorten task_id for table display."""
    if "__" in task_id:
        # Take the hash part after the repo name
        after_org = task_id.split("__")[1]
        parts = after_org.split("-")
        if len(parts) >= 2:
            # repo-hashpart-vhash → just hashpart[:8]
            hash_part = parts[1][:8] if len(parts[1]) > 8 else parts[1]
            return f"{parts[0][:12]}-{hash_part}…"
    return task_id[:max_len]


def print_table(results, errors, label=None):
    """Print console table of audit results."""
    if label:
        print(f"\n{'='*80}")
        print(f"  {label}")
        print(f"{'='*80}")

    # Print errors first
    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    {e.get('task_id', '?')}: {e.get('error', '?')}")

    # Table header
    print()
    hdr = f"  {'Repo':<14} {'Task':<22} {'RJ':>5} {'True':>5} {'Category':<16} {'FTP P/F/NR':>12} {'Detail'}"
    print(hdr)
    print(f"  {'-'*14} {'-'*22} {'-'*5} {'-'*5} {'-'*16} {'-'*12} {'-'*30}")

    # Sort by repo then category
    for r in sorted(results, key=lambda x: (x["repo"], x["category"], x["task_id"])):
        repo = r["repo"][:14]
        task = _short_task(r["task_id"], 22)
        rj = "TRUE" if r["rj_resolved"] else "FALSE"
        true = "TRUE" if r["true_resolved"] else "FALSE"
        cat = r["category"]
        if r["subcategory"]:
            cat = r["subcategory"]
        pnf = f"{r['ftp_passed']}/{r['ftp_failed']}/{r['ftp_not_found']}"
        if r.get("ftp_not_exist", 0):
            pnf += f"/{r['ftp_not_exist']}"
        detail = r["detail"][:40]
        print(f"  {repo:<14} {task:<22} {rj:>5} {true:>5} {cat:<16} {pnf:>12} {detail}")


def print_summary(results, errors, label=None):
    """Print summary statistics."""
    total = len(results)
    tp = sum(1 for r in results if r["category"] == "TRUE-POSITIVE")
    tn = sum(1 for r in results if r["category"] == "TRUE-NEGATIVE")
    fn = sum(1 for r in results if r["category"] == "FALSE-NEGATIVE")
    fp = sum(1 for r in results if r["category"] == "FALSE-POSITIVE")

    rj_resolved = sum(1 for r in results if r["rj_resolved"])
    true_resolved = sum(1 for r in results if r["true_resolved"])

    print(f"\n  SUMMARY{' — ' + label if label else ''}")
    print(f"  {'─'*50}")
    print(f"  Total audited:    {total:>4} tasks ({len(errors)} errors)")
    print(f"  TRUE-POSITIVE:    {tp:>4} (correctly resolved)")
    print(f"  TRUE-NEGATIVE:    {tn:>4} (correctly not resolved)")
    print(f"  FALSE-NEGATIVE:   {fn:>4} (should be resolved, marked not)")
    print(f"  FALSE-POSITIVE:   {fp:>4} (should not be resolved, marked yes)")
    print()
    print(f"  result.json score:  {rj_resolved}/{total}")
    print(f"  Corrected score:    {true_resolved}/{total}")
    if rj_resolved != true_resolved:
        diff = true_resolved - rj_resolved
        sign = "+" if diff > 0 else ""
        print(f"  Delta:              {sign}{diff}")

    # Sub-category breakdown
    subcats = {}
    for r in results:
        sc = r.get("subcategory")
        if sc:
            subcats[sc] = subcats.get(sc, 0) + 1
    if subcats:
        print(f"\n  Sub-categories:")
        for sc, count in sorted(subcats.items()):
            print(f"    {sc:<20} {count:>3}")

    # Per-repo breakdown
    repo_stats = {}
    for r in results:
        repo = r["repo"]
        if repo not in repo_stats:
            repo_stats[repo] = {"total": 0, "rj": 0, "true": 0, "fn": 0, "fp": 0}
        repo_stats[repo]["total"] += 1
        if r["rj_resolved"]:
            repo_stats[repo]["rj"] += 1
        if r["true_resolved"]:
            repo_stats[repo]["true"] += 1
        if r["category"] == "FALSE-NEGATIVE":
            repo_stats[repo]["fn"] += 1
        if r["category"] == "FALSE-POSITIVE":
            repo_stats[repo]["fp"] += 1

    print(f"\n  Per-repo breakdown:")
    print(f"  {'Repo':<14} {'Total':>5} {'RJ':>5} {'True':>5} {'FN':>4} {'FP':>4}")
    print(f"  {'-'*14} {'-'*5} {'-'*5} {'-'*5} {'-'*4} {'-'*4}")
    for repo in sorted(repo_stats):
        s = repo_stats[repo]
        print(f"  {repo:<14} {s['total']:>5} {s['rj']:>5} {s['true']:>5} {s['fn']:>4} {s['fp']:>4}")


def write_json_report(results, errors, output_path, label=None):
    """Write full JSON report."""
    report = {
        "label": label,
        "total": len(results),
        "errors": errors,
        "results": results,
        "summary": {
            "true_positive": sum(1 for r in results if r["category"] == "TRUE-POSITIVE"),
            "true_negative": sum(1 for r in results if r["category"] == "TRUE-NEGATIVE"),
            "false_negative": sum(1 for r in results if r["category"] == "FALSE-NEGATIVE"),
            "false_positive": sum(1 for r in results if r["category"] == "FALSE-POSITIVE"),
            "rj_resolved": sum(1 for r in results if r["rj_resolved"]),
            "true_resolved": sum(1 for r in results if r["true_resolved"]),
        },
    }
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  JSON report written to: {output_path}")


def write_csv_report(results, output_path):
    """Write CSV report with one row per task."""
    fieldnames = [
        "repo", "task_id", "rj_resolved", "true_resolved", "category",
        "subcategory", "ftp_count", "ftp_passed", "ftp_failed",
        "ftp_not_found", "ftp_not_exist", "early_stop", "crash_type", "detail",
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(results, key=lambda x: (x["repo"], x["task_id"])):
            writer.writerow(r)
    print(f"  CSV report written to: {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Deep audit of SWE-bench Pro evaluation artifacts"
    )
    parser.add_argument(
        "--artifact-dir", required=True,
        help="Directory containing artifact folders (each with result.json, verification.log)"
    )
    parser.add_argument(
        "--task-yaml-dir", required=True,
        help="Root datasets directory (e.g. /path/to/eval-runner/datasets)"
    )
    parser.add_argument(
        "--label", default=None,
        help="Label for this audit run (e.g. 'Claude opus-4-6 (100 tasks)')"
    )
    parser.add_argument(
        "--output-json", default=None,
        help="Path to write JSON report"
    )
    parser.add_argument(
        "--output-csv", default=None,
        help="Path to write CSV report"
    )
    parser.add_argument(
        "--show-false-only", action="store_true",
        help="Only show FALSE-NEGATIVE and FALSE-POSITIVE results in table"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show per-test details for mismatches"
    )

    args = parser.parse_args()

    results, errors = audit_artifact_dir(
        args.artifact_dir, args.task_yaml_dir, args.label
    )

    if not results and not errors:
        print("No artifacts found to audit.")
        return

    # Filter for display if requested
    display_results = results
    if args.show_false_only:
        display_results = [
            r for r in results
            if r["category"] in ("FALSE-NEGATIVE", "FALSE-POSITIVE")
        ]

    print_table(display_results, errors, args.label)
    print_summary(results, errors, args.label)

    if args.verbose:
        # Print details for FALSE-NEGATIVE and FALSE-POSITIVE
        mismatches = [
            r for r in results
            if r["category"] in ("FALSE-NEGATIVE", "FALSE-POSITIVE")
        ]
        if mismatches:
            print(f"\n  MISMATCH DETAILS:")
            print(f"  {'─'*60}")
            for r in mismatches:
                print(f"\n  {r['category']} | {r['repo']} | {r['task_id']}")
                print(f"    result.json: resolved={r['rj_resolved']}")
                print(f"    audit:       resolved={r['true_resolved']}")
                if r.get("crash_type"):
                    print(f"    crash:       {r['crash_type']}")
                if r.get("failed_tests"):
                    print(f"    failed:      {r['failed_tests'][:3]}")
                if r.get("not_found_tests"):
                    print(f"    not found:   {r['not_found_tests'][:3]}")
                if r.get("not_exist_tests"):
                    print(f"    not exist:   {r['not_exist_tests'][:3]}")

    if args.output_json:
        write_json_report(results, errors, args.output_json, args.label)

    if args.output_csv:
        write_csv_report(results, args.output_csv)


if __name__ == "__main__":
    main()
