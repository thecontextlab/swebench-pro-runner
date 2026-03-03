# Docker Images

SWE-bench Pro Runner uses prebaked Docker images with all dependencies pre-installed. Each repository has one or more images that contain the target codebase's build tools, test frameworks, and AI agent CLIs.

## Image Registry

All images are hosted on GitHub Container Registry (GHCR):

```
ghcr.io/thecontextlab/swebench-pro-{repo}:{tag}
```

## Image Catalog

### Standard Images

| Repository | Image | Language | Base | Tag |
|------------|-------|----------|------|-----|
| vuls | `swebench-pro-vuls` | Go | Ubuntu + Go 1.21 | `multi-agent` |
| flipt | `swebench-pro-flipt` | Go | Ubuntu + Go 1.21 | `multi-agent` |
| navidrome | `swebench-pro-navidrome` | Go | Ubuntu + Go 1.21 | `multi-agent` |
| teleport | `swebench-pro-teleport` | Go | Ubuntu + Go 1.22 | `multi-agent` |
| ansible | `swebench-pro-ansible` | Python | Ubuntu + Python 3.9 | `multi-agent` |
| openlibrary | `swebench-pro-openlibrary` | Python | Ubuntu + Python 3.10 | `multi-agent` |
| qutebrowser | `swebench-pro-qutebrowser` | Python | Ubuntu + Python 3.10 | `multi-agent` |
| element-web | `swebench-pro-element-web` | TypeScript | Ubuntu + Node.js 20 | `multi-agent` |
| webclients | `swebench-pro-webclients` | TypeScript | Ubuntu + Node.js 20 | `multi-agent` |
| NodeBB | `swebench-pro-NodeBB` | JavaScript | Ubuntu + Node.js 20 | `multi-agent` |
| tutanota | `swebench-pro-tutanota` | TypeScript | Ubuntu + Node.js 20 | `multi-agent` |

### Variant Images

Some repositories require multiple images for different task groups:

| Repository | Variant | Image | Purpose |
|------------|---------|-------|---------|
| ansible | Python 3.9 | `swebench-pro-ansible:multi-agent` | Legacy tasks (pre-2022) |
| ansible | Python 3.9 (alt) | `swebench-pro-ansible-python39:multi-agent` | Alternate Python 3.9 build |
| openlibrary | Python 3.9 | `swebench-pro-openlibrary-python39:multi-agent` | Legacy tasks |
| openlibrary | Python 3.9 (fixed) | `swebench-pro-openlibrary-python39-fixed:multi-agent` | Patched legacy build |
| openlibrary | Python 3.11 | `swebench-pro-openlibrary-python311:multi-agent` | Modern tasks |
| openlibrary | Python 3.11 (fixed) | `swebench-pro-openlibrary-python311-fixed:multi-agent` | Patched modern build |
| openlibrary | Python 3.12 | `swebench-pro-openlibrary-python312:multi-agent` | Latest tasks |
| qutebrowser | Python 3.10 | `swebench-pro-qutebrowser:multi-agent` | Default |
| qutebrowser | Python 3.11 | `swebench-pro-qutebrowser-python311:multi-agent` | Modern tasks |
| tutanota | Base | `swebench-pro-tutanota:multi-agent` | Default |
| tutanota | Node 18 | `swebench-pro-tutanota-node18:multi-agent` | Legacy Node.js 18 tasks |
| tutanota | Node 20 | `swebench-pro-tutanota-node20:multi-agent` | Node.js 20 tasks |
| webclients | Default | `swebench-pro-webclients:multi-agent` | Default |
| webclients | Karma | `swebench-pro-webclients-karma:multi-agent` | Karma test runner tasks |
| webclients | Node 22 | `swebench-pro-webclients-node22:multi-agent` | Node.js 22 tasks |

Task-to-image routing is handled by `config_loader.py` using patterns defined in each repository's `config.yaml`. See [ARCHITECTURE.md](ARCHITECTURE.md) for the configuration hierarchy.

## What's Inside Each Image

Every image includes:

### Operating System and Runtime

- Ubuntu 22.04 LTS base
- Language runtime (Go, Python, or Node.js) at the required version
- Build essentials (gcc, make, git, curl, etc.)
- Common utilities (jq, yq, tar, zip)

### AI Agent CLIs

All `multi-agent` tagged images include:

| Agent CLI | Version | Install Method |
|-----------|---------|---------------|
| Claude Code (`claude`) | Latest | `npm install -g @anthropic-ai/claude-code` |
| Codex CLI (`codex`) | Latest | `npm install -g @openai/codex` |
| Gemini CLI (`gemini`) | Latest | `npm install -g @anthropic-ai/gemini-cli` |

Node.js 20 is installed on all images (even Python/Go repos) to support the agent CLIs.

### Repository-Specific Dependencies

Each image pre-installs the target repository's dependencies:

- **Go repos**: `go mod download` with cached modules
- **Python repos**: `pip install` with pre-populated virtualenv
- **Node.js repos**: `npm ci` with `node_modules` populated

## Pulling Images

### Authentication

GHCR images require authentication:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u USERNAME --password-stdin
```

In GitHub Actions, `GITHUB_TOKEN` is automatically available.

### Pull Command

```bash
docker pull ghcr.io/thecontextlab/swebench-pro-vuls:multi-agent
```

## Dockerfiles

All Dockerfiles are in the `docker/` directory at the repository root. Each file follows the naming convention `Dockerfile.{repo-variant}`:

```
docker/
├── Dockerfile.ansible-multi-agent
├── Dockerfile.ansible-python39-multi-agent
├── Dockerfile.element-web-multi-agent
├── Dockerfile.flipt
├── Dockerfile.navidrome-multi-agent
├── Dockerfile.nodebb-multi-agent
├── Dockerfile.openlibrary-python39
├── Dockerfile.openlibrary-python39-fixed
├── Dockerfile.openlibrary-python311
├── Dockerfile.openlibrary-python311-fixed
├── Dockerfile.openlibrary-python312
├── Dockerfile.qutebrowser-multi-agent
├── Dockerfile.qutebrowser-python311-multi-agent
├── Dockerfile.teleport
├── Dockerfile.tutanota
├── Dockerfile.tutanota-multi-agent
├── Dockerfile.tutanota-node18
├── Dockerfile.tutanota-node20
├── Dockerfile.vuls-multi-agent
├── Dockerfile.webclients
├── Dockerfile.webclients-karma
├── Dockerfile.webclients-node22
└── build.sh                          # Local build helper script
```

## Building Images

### Using the Build Script

The `docker/build.sh` helper script simplifies building and pushing images:

```bash
# Build one image
./docker/build.sh vuls-multi-agent

# Build and push to GHCR
./docker/build.sh --push flipt

# Build all images
./docker/build.sh --all

# Fresh rebuild (no Docker cache)
./docker/build.sh --no-cache teleport

# List all available Dockerfiles and their image names
./docker/build.sh --list
```

### Using the GitHub Actions Workflow

The `docker-build.yml` workflow builds images in CI:

1. Go to **Actions → Build Docker Image**
2. Select the Dockerfile from the dropdown
3. Optionally enable **push** to publish to GHCR
4. Optionally enable **no_cache** for fresh rebuilds

The workflow auto-derives the GHCR image name from the Dockerfile suffix, verifies tools after build, and generates a summary report.

### Dockerfile Structure

```dockerfile
FROM ubuntu:22.04

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential git curl wget jq \
    && rm -rf /var/lib/apt/lists/*

# Language runtime
# Go example:
RUN wget https://go.dev/dl/go1.21.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.21.linux-amd64.tar.gz && \
    rm go1.21.linux-amd64.tar.gz
ENV PATH="/usr/local/go/bin:${PATH}"

# Python example:
# RUN apt-get install -y python3.11 python3.11-venv python3-pip

# Node.js (required for agent CLIs)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# AI Agent CLIs
RUN npm install -g @anthropic-ai/claude-code @openai/codex

# Pre-install repository dependencies
WORKDIR /testbed
COPY go.mod go.sum ./
RUN go mod download

# Set working directory
WORKDIR /testbed
```

### Build and Push

```bash
# Build
docker build -t ghcr.io/thecontextlab/swebench-pro-vuls:multi-agent .

# Push
docker push ghcr.io/thecontextlab/swebench-pro-vuls:multi-agent
```

### Verifying an Image

```bash
# Test that the image has all required tools
docker run --rm ghcr.io/thecontextlab/swebench-pro-vuls:multi-agent \
  bash -c "go version && claude --version && node --version"
```

## Creating Images for New Repositories

### Step 1: Analyze the Repository

Determine:
- Primary language and runtime version
- Build system (make, npm, go build, etc.)
- Test framework (pytest, go test, jest, etc.)
- System dependencies

### Step 2: Write the Dockerfile

Start from the closest existing image and adapt:

```bash
# Copy an existing Dockerfile as starting point
cp docker/Dockerfile.vuls-multi-agent docker/Dockerfile.newrepo-multi-agent
```

### Step 3: Pre-install Dependencies

Run the repository's dependency installation inside the image:

```dockerfile
# Clone and install dependencies during build
RUN git clone https://github.com/org/repo.git /testbed && \
    cd /testbed && \
    go mod download  # or: npm ci / pip install -e .
```

### Step 4: Build and Test

```bash
# Build the image
docker build -t ghcr.io/thecontextlab/swebench-pro-newrepo:multi-agent \
  -f docker/Dockerfile.newrepo-multi-agent .

# Test it works
docker run --rm -it ghcr.io/thecontextlab/swebench-pro-newrepo:multi-agent bash
# Inside container:
cd /testbed && go test ./... # or: pytest / npm test
```

### Step 5: Push to GHCR

```bash
docker push ghcr.io/thecontextlab/swebench-pro-newrepo:multi-agent
```

### Step 6: Configure

Create `datasets/newrepo/config.yaml`:

```yaml
repository: org/repo
language: go  # or python, typescript, javascript

image: ghcr.io/thecontextlab/swebench-pro-newrepo:multi-agent

workdir: /testbed
timeout_minutes: 45

agent:
  type: claude-code
  default_model: claude-sonnet-4-5-20250929

tasks:
  count: 0
  pattern: org__repo-*
```

### Step 7: Add to Workflow

Add the new repository to the dropdown in `swebench-eval.yml`:

```yaml
inputs:
  repo:
    type: choice
    options:
      - vuls
      - newrepo  # Add here
```

## MCP Images

For A/B testing with MCP servers, separate images can be built with MCP server data pre-indexed. These extend the base images:

```dockerfile
FROM ghcr.io/thecontextlab/swebench-pro-vuls:multi-agent

# Add MCP server data
COPY index-data/ /opt/mcp/data/
ENV MCP_DATA_DIR=/opt/mcp/data
```

MCP images are optional and only needed if running an MCP server alongside the agent in the same container. Most MCP setups use external HTTP servers configured via `config.yaml`.

## Design Decisions

### Hybrid images vs upstream per-task Dockerfiles

The upstream [SWE-bench_Pro-os](https://github.com/scaleapi/SWE-bench_Pro-os) project uses **1,462 Dockerfiles** (2 per task: a base + an instance Dockerfile) to produce per-task Docker images pre-built on Docker Hub. Each task gets an immutable, isolated image with the exact repo commit, dependency snapshot (via `pypi-timemachine`), and build artifacts baked in. Under the hood, these collapse to ~50 unique base image tags and ~69 unique base Dockerfile contents — but the project still ships and manages all 731 instance images.

We took a different approach: **22 repo-level Dockerfiles** producing variant images, combined with **731 per-task `setup.sh` scripts** that handle task-specific provisioning at runtime. This was driven by three factors:

1. **Multi-agent CLI compatibility.** All three agent CLIs (Claude Code, Codex, Gemini) require Node.js 20+. The upstream images don't include agent CLIs at all — they're evaluation-only. We needed Node.js 20 on every image (including Python and Go repos), plus three globally-installed npm packages (`@anthropic-ai/claude-code`, `@openai/codex`, `@google/gemini-cli`). Managing CLI version updates across 731 images would be impractical; with 22 images, a rebuild cycle takes minutes.

2. **Infrastructure failure reduction.** An audit of 742 setup scripts found 136 infrastructure failures: 107 from network timeouts (Yarn/NPM registry), 15 from missing build dependencies, and 10 from directory structure issues. Pre-installing common dependencies (Yarn Berry config, CGO libraries, image libraries) in the base image eliminated 90% of these failures and reduced per-task initialization from 3-5 minutes to 10-30 seconds.

3. **Operational simplicity.** 22 Dockerfiles are reviewable and maintainable by a small team. The config_loader.py routing system (task groups with regex patterns → image selection) provides the same task-to-image mapping that the upstream project achieves with 731 instance Dockerfiles.

The tradeoff: our images are larger (2-5 GB vs ~1-2 GB upstream) because they include all three agent CLIs and broader dependency caches. But evaluations start faster since most dependencies are already installed.

### Future direction: sidecar agent CLIs

A potential evolution is a **sidecar pattern** where agent CLIs run in a separate container alongside the repo image. This would:
- Decouple agent CLI versions from repo environment setup
- Allow repo images to match the upstream per-task approach (exact runtime, no Node.js 20 pollution)
- Enable independent agent CLI updates without rebuilding repo images
- Support running different CLI versions in the same evaluation batch

This is tracked in [ADR-013](https://github.com/thecontextlab/swebench-pro-runner/issues/28).

### Why openlibrary has 5+ image variants

OpenLibrary tasks span multiple years of development. The codebase migrated from Python 3.9 to 3.11 to 3.12 over time, and task-specific dependencies are pinned via `pypi-timemachine` to dates ranging from 2021 to 2024. A task from 2021 may depend on packages that only install correctly under Python 3.9 with `timemachine_date: "2021-02-01"`, while a 2024 task requires Python 3.12 APIs with `timemachine_date: "2024-10-17"`. The `-fixed` variants include patches for dependency resolution issues discovered during infrastructure validation — specifically, pip version conflicts and broken package metadata in older PyPI snapshots.

Task routing is defined in `datasets/openlibrary/config.yaml` with 5 task groups, each mapping commit-hash regex patterns to the appropriate Python version image.

### Why element-web patches Node shebangs

The element-web test suite uses jsdom 16, which crashes on Node.js 20 due to breaking changes in V8's internal APIs. The Dockerfile uses a dual-Node approach:

1. Save the Node 20 binary to `/usr/local/bin/node20`
2. Install Node 18 via `n` version manager as the default `node`
3. Patch all three agent CLI entry points (claude, codex, gemini) to use `#!/usr/local/bin/node20` instead of `#!/usr/bin/env node`

This means project tests run with Node 18 (jsdom-compatible) while agent CLIs use Node 20 (their minimum requirement). The shebang patching is done at image build time via `sed -i` on the resolved symlink targets.

### Why webclients requires Node 22 and has a karma variant

The WebClients monorepo's `package.json` requires Node `>= 22.14.0`. Earlier Node versions produce `Iterator is not defined` errors from jsdom 16's polyfill interacting with core-js. The base `webclients-node22` image also handles several historical compatibility issues:

- **Yarn version mismatch**: The baked image uses Yarn 4.12.0, but historical task commits have Yarn 3.6.0 lockfiles. The Dockerfile saves the baked Yarn config to `/opt/` so `setup.sh` can restore it after `git reset --hard` to an older commit.
- **Removed packages**: 8 packages that existed in older commits but were removed at HEAD (jsbi, react-sortable-hoc, pmcrypto-v7, etc.) are pre-installed into `/testbed/node_modules` to avoid import failures during historical test runs.
- **Jest-dom exports**: `@testing-library/jest-dom` subpath exports are patched to support legacy import patterns.

The **karma variant** (`webclients-karma`) is a separate image for a single task that requires the Karma test runner with Chromium. It adds puppeteer 22.0.0, playwright 1.45.0, and the Playwright Chromium binary — roughly 300 MB of dependencies that would bloat the default image for 64 tasks that don't need them.

### Why tutanota has 4 image variants

Tutanota tasks require different Node.js versions because the codebase has native module dependencies with specific V8 API requirements:

- **Node 22 (default)**: Current master uses `@signalapp/sqlcipher` which is Node 22 compatible
- **Node 20**: Middle-ground variant for tasks using `better-sqlite3` and `keytar` (incompatible with Node 22 due to V8 API changes)
- **Node 18**: Legacy tasks with older native module versions

All variants include Rust 1.84.0 (for native module compilation) and Emscripten 3.1.59 (for WebAssembly compilation of crypto libraries). Git submodules (liboqs, argon2, Signal-FTS5-Extension) are initialized at build time.

The root cause analysis is documented in `eval-runner/tutanota_docker_fix_rca.md`: node-gyp compilation failures, missing Emscripten/Rust prerequisites, and `globalThis.crypto` read-only property assignment errors across Node versions.

### Version Policy

Agent CLI versions are pinned in Dockerfiles to ensure reproducible evaluations:

| CLI | Current Pin | Install Method |
|-----|-------------|---------------|
| Claude Code (`claude`) | `@anthropic-ai/claude-code@2.1.42` | `npm install -g` |
| Codex CLI (`codex`) | `@openai/codex@0.101.0` | `npm install -g` |
| Gemini CLI (`gemini`) | `@google/gemini-cli@0.28.2` | `npm install -g` |

All multi-agent images verify CLI installation at build time with `which claude && which codex && which gemini`. To update, rebuild all images with `--no-cache` (see [Image Maintenance](#image-maintenance) below). Automated staleness tracking is planned in [ADR-011](https://github.com/thecontextlab/swebench-pro-runner/issues/26).

### Prebake vs Runtime Split

The platform uses a hybrid strategy where Docker images contain stable, expensive-to-install dependencies while per-task `setup.sh` scripts handle task-specific runtime configuration. This was derived from auditing the upstream SWE-bench_Pro-os instance Dockerfiles: their `/build.sh` scripts (baked into per-task images) contain the same operations our `setup.sh` scripts run at evaluation time.

**Prebaked in Dockerfile** (changes rarely, expensive to install):
- System packages (`apt-get install build-essential git curl wget jq`)
- Language runtimes (Go 1.21/1.22, Python 3.9/3.10/3.11/3.12, Node.js 18/20/22)
- AI agent CLIs (claude, codex, gemini — require Node.js 20+)
- Dependency caches (`go mod download`, base pip packages, `node_modules`)
- Build toolchains (Rust, Emscripten for tutanota; CGO libraries for Go repos)

**Runtime in setup.sh** (changes per task, derived from upstream instance Dockerfiles):
- Git repository state (`git reset --hard` to base_commit, `git clean -fdx`)
- Task-specific `pip install` with `pypi-timemachine` date constraints
- `npm ci` or `yarn install` with task-specific lockfiles
- Service startup (Redis for NodeBB, etc.)
- Virtual environment activation and build steps (`make setup`, `node app --setup`, etc.)

Only 4 of 11 repos (navidrome, vuls, flipt, element-web) have consistent build commands across all tasks. The other 7 repos require task-specific provisioning — the primary reason per-task `setup.sh` scripts exist.

## Image Maintenance

### Updating Agent CLIs

When new agent CLI versions are released:

```bash
# Rebuild all images with latest CLIs
for repo in vuls flipt teleport navidrome ansible openlibrary qutebrowser \
            element-web webclients NodeBB tutanota; do
  docker build --no-cache \
    -t ghcr.io/thecontextlab/swebench-pro-${repo}:multi-agent \
    -f docker/Dockerfile.${repo}-multi-agent .
  docker push ghcr.io/thecontextlab/swebench-pro-${repo}:multi-agent
done
```

### Image Size Guidelines

- Target image size: 2-5 GB (pre-installed dependencies reduce eval startup time)
- Use multi-stage builds if build dependencies are much larger than runtime
- Always clean apt caches: `rm -rf /var/lib/apt/lists/*`
- For Go repos, `go mod download` caches are acceptable (fast restore)
