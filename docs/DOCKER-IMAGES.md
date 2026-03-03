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

### Why openlibrary has 5+ image variants

OpenLibrary tasks span multiple years of development. Different task cohorts require different Python versions because the codebase migrated from Python 3.9 to 3.11 to 3.12 over time. A task from 2022 may depend on packages that only install correctly under Python 3.9, while a 2024 task requires Python 3.12 APIs. The `-fixed` variants include patches for dependency resolution issues specific to older Python builds.

### Why element-web patches Node shebangs

The element-web test suite uses jsdom 16, which crashes on Node.js 20 due to breaking changes in the `structuredClone` API. The Dockerfile installs Node 18 for running tests while saving a Node 20 binary at a separate path for the AI agent CLIs (which require Node 20+). Shebang patching ensures test scripts use the correct Node version.

### Why webclients has a karma variant

Most webclients tasks use Jest, but a subset of tasks in the ProtonMail WebClients monorepo use the Karma test runner. The `webclients-karma` image pre-installs Karma, Chrome headless, and related dependencies that would bloat the default image.

### Why tutanota has 4 image variants

Tutanota tasks require different Node.js versions (18, 20, 22) because the Emscripten and Rust WebAssembly build toolchains have specific Node version requirements. Tasks targeting older Emscripten versions need Node 18, while newer builds require Node 20 or 22.

### Version Policy

Agent CLI versions are pinned in Dockerfiles to ensure reproducible evaluations. Current pins:

| CLI | Version | Update Frequency |
|-----|---------|-----------------|
| Claude Code (`claude`) | Pinned per Dockerfile | Manual rebuild on new release |
| Codex CLI (`codex`) | Pinned per Dockerfile | Manual rebuild on new release |
| Gemini CLI (`gemini`) | Pinned per Dockerfile | Manual rebuild on new release |

To update, rebuild all images with `--no-cache` (see [Image Maintenance](#image-maintenance) below). Automated staleness tracking is planned in [ADR-011](https://github.com/thecontextlab/swebench-pro-runner/issues/26).

### Prebake vs Runtime Split

The platform uses a hybrid strategy: Docker images contain stable, expensive-to-install dependencies while `setup.sh` handles task-specific runtime configuration.

**Prebaked in Dockerfile** (changes rarely):
- System packages (`apt-get install`)
- Language runtimes (Go, Python, Node.js)
- AI agent CLIs (claude, codex, gemini)
- Dependency caches (`go mod download`, base pip packages, `node_modules`)

**Runtime in setup.sh** (changes per task):
- Git repository state (`git reset --hard` to base_commit)
- Task-specific `pip install` with `--timemachine-date` constraints
- `npm ci` with task-specific `package.json`
- Virtual environment activation and configuration

This split means images are large (2-5 GB) but evaluations start fast — most dependencies are already installed. Only task-specific setup runs at evaluation time.

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
