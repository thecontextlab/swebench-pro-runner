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
| ansible | Python 3.11 | `swebench-pro-ansible-python311:multi-agent` | Modern tasks |
| openlibrary | Python 3.9 | `swebench-pro-openlibrary:multi-agent` | Legacy tasks |
| openlibrary | Python 3.11 | `swebench-pro-openlibrary-python311:multi-agent` | Modern tasks |
| openlibrary | Python 3.12 | `swebench-pro-openlibrary-python312:multi-agent` | Latest tasks |

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
├── Dockerfile.openlibrary-python311
├── Dockerfile.openlibrary-python39
├── Dockerfile.qutebrowser-multi-agent
├── Dockerfile.teleport
├── Dockerfile.tutanota-multi-agent
├── Dockerfile.vuls-multi-agent
├── Dockerfile.webclients
└── Dockerfile.webclients-node22
```

## Building Images

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
