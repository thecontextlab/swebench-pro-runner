# Architecture

This platform is built on the [SWE-bench Pro](https://arxiv.org/abs/2509.16941) benchmark by Scale AI. Task definitions are derived from the public dataset ([ScaleAI/SWE-bench_Pro](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro)).

## System Overview

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────────┐     ┌─────────────┐
│   User/CLI   │────▶│  GitHub Actions  │────▶│   Docker Container   │────▶│  Artifacts  │
│              │     │ swebench-eval.yml│     │  (prebaked image)    │     │  result.json │
│ gh workflow  │     │                  │     │  /testbed + agent    │     │  agent.log   │
│ run ...      │     │  ubuntu-latest   │     │                     │     │  *.patch     │
└──────────────┘     └─────────────────┘     └──────────────────────┘     └─────────────┘
                                                                                │
                     ┌─────────────────┐                                        │
                     │  Orchestration   │◀───────────────────────────────────────┘
                     │  Scripts         │     Download, validate, report
                     │  (local Python)  │
                     └─────────────────┘
```

## Evaluation Pipeline

The `swebench-eval.yml` workflow executes a 10-step pipeline for each task:

### Step 0: Checkout and Configuration

```
Checkout repo → Install yq → Load task YAML → Resolve config
```

The workflow loads the task YAML from `datasets/{repo}/tasks/{task_id}.yaml`, then uses `config_loader.py` to resolve the Docker image and metadata.

### Step 1: Clone Repository

```bash
git clone "$REPO_URL" /testbed
```

The target repository is cloned fresh into `/testbed` inside the container.

### Step 2: Set Repository State (`before_repo_set_cmd`)

```bash
git reset --hard {base_commit}
git clean -fd
git checkout {base_commit}
git checkout {task_commit} -- path/to/test_file
```

Resets the repo to the base commit and applies test patches so that fail-to-pass tests exist but the fix code doesn't.

### Step 3: Provision Environment (`setup.sh`)

The task-specific setup script installs dependencies, configures build tools, and prepares the environment.

### Step 4: Pre-Verification (F2P)

```bash
VERIFICATION_PHASE=pre /run_script.sh "${FAIL_TO_PASS[@]}"
```

Runs fail-to-pass tests to confirm they fail before the agent runs. If tests pass at this stage, the task may be invalid.

### Step 4b: Pre-Verification (P2P)

```bash
VERIFICATION_PHASE=pre /run_script.sh "${PASS_TO_PASS[@]}"
```

Runs pass-to-pass tests to confirm they pass before the agent runs. This establishes the baseline for regression detection.

### Step 5: Run AI Agent

```bash
python3 /run_agent.py 2>&1 | tee /results/agent.log
```

The selected agent wrapper (`run_claude.py`, `run_codex.py`, or `run_gemini.py`) executes with the task instruction. The agent has access to the codebase at `/testbed` and produces changes to fix the failing tests.

### Step 6: Create Patch

```bash
git diff > /results/changes.patch
```

Captures all modifications the agent made as a git diff.

### Step 7: Post-Verification (F2P)

```bash
VERIFICATION_PHASE=post /run_script.sh "${FAIL_TO_PASS[@]}"
```

Runs the same fail-to-pass tests again. If they pass now, the agent has resolved the task.

### Step 8: Post-Verification (P2P)

```bash
VERIFICATION_PHASE=post /run_script.sh "${PASS_TO_PASS[@]}"
```

Runs pass-to-pass tests to check for regressions.

### Step 9: Metrics Extraction

```bash
python3 datasets/{repo}/extract_metrics.py
```

Parses `agent.log`, `verification.log`, and `changes.patch` to produce the enhanced `result.json`. See [ANALYTICS.md](ANALYTICS.md) for the full schema.

### Step 10: Upload Artifacts

Results are uploaded as GitHub Actions artifacts with 90-day retention:
```
swebench-result-{task_id}-{run_id}-{run_number}/
├── result.json
├── agent.log
├── changes.patch
├── pre_verification.log
├── verification.log
├── p2p_pre_verification.log
└── p2p_verification.log
```

## Workflows

### `swebench-eval.yml` — Main Evaluation

The primary workflow. Accepts inputs:

| Input | Required | Description |
|-------|----------|-------------|
| `repo` | Yes | Target repository (dropdown of 11 options) |
| `task` | Yes | Full task ID string |
| `agent` | No | `claude`, `codex`, or `gemini` (default: `claude`) |
| `model` | No | Model identifier (default: `claude-sonnet-4-5-20250929`) |
| `enable_mcp` | No | Enable MCP server (default: `false`) |
| `anthropic_api_key` | No | Override API key (falls back to secret) |
| `openai_api_key` | No | Override API key (falls back to secret) |
| `gemini_api_key` | No | Override API key (falls back to secret) |
| `timeout_minutes` | No | Job timeout in minutes (default: 60) |
| `agent_timeout_minutes` | No | Agent step timeout in minutes (default: 45) |
| `max_turns` | No | Maximum agent turns, 0 = unlimited (default: 0) |

Runs on `ubuntu-latest`. Job timeout and agent timeout are configurable via inputs (defaults: 60 and 45 minutes respectively). Concurrency is scoped per-actor per-repo to prevent duplicate runs.

### `regression-test.yml` — P2P Regression Testing

A focused workflow that applies a previously-generated patch and runs only pass-to-pass tests. Used to validate that a fix doesn't introduce regressions, without re-running the agent.

Five-phase pipeline:
1. **Setup**: Load task config, pull Docker image
2. **Repo Prep**: Clone, apply `before_repo_set_cmd`, run `setup.sh`
3. **Apply Patch**: Apply the agent's `changes.patch`
4. **Run P2P Tests**: Execute pass-to-pass tests
5. **Report**: Generate regression result

### `validate-infrastructure.yml` — Infrastructure Validation

A zero-cost workflow that validates Docker images, repo setup, and test baselines without running an AI agent. Useful for verifying infrastructure before launching expensive evaluation runs.

Four-phase validation:
1. **Image Pull**: Pull Docker image from GHCR, verify basic tools (git, bash)
2. **Repo Setup**: Clone repo, apply `before_repo_set_cmd`, run `setup.sh`
3. **F2P Pre-verification**: Confirm fail-to-pass tests fail (validates task correctness)
4. **P2P Baseline**: Confirm pass-to-pass tests pass (validates infrastructure)

Inputs: `repo` (dropdown), `task` (optional), `validation_type` (`all`/`image`/`setup`/`f2p`/`p2p`), `timeout_minutes`. Outputs a `validation_report.json` artifact with pass/fail/warn per phase.

### `docker-build.yml` — Docker Image Build

Builds and optionally pushes Docker images from `docker/Dockerfile.*` files. Supports all 22 Dockerfiles via a dropdown input.

Inputs: `dockerfile` (dropdown), `push` (boolean, default false), `no_cache` (boolean), `platform` (`linux/amd64` or `linux/arm64`). Auto-derives the GHCR image name from the Dockerfile suffix. Verifies tools after build.

A local helper script `docker/build.sh` provides the same functionality outside GitHub Actions.

## Container Filesystem Layout

```
/
├── testbed/              # Cloned target repository (agent workspace)
├── results/              # Output directory (mounted volume)
│   ├── result.json
│   ├── agent.log
│   ├── changes.patch
│   ├── pre_verification.log
│   ├── verification.log
│   ├── p2p_pre_verification.log
│   └── p2p_verification.log
├── instruction.txt       # Task instruction (read-only mount)
├── before_repo_set_cmd.txt  # Git setup commands
├── fail_to_pass.txt      # F2P test names (one per line)
├── pass_to_pass.txt      # P2P test names (one per line)
├── run_script.sh         # Test execution script
├── setup.sh              # Environment provisioning script
├── run_agent.py          # Agent wrapper (read-only mount)
└── base_agent_adapter.py # Base class for agents
```

All file mounts are read-only except `/results` which is a writable volume mapped back to the host.

## Configuration System

### Three-Level Hierarchy

Configuration resolves through three levels (highest priority first):

```
Task Override  →  Task Group  →  Repository Default
```

This is implemented by `TaskImageResolver` in `datasets/common/config_loader.py`:

```python
class TaskImageResolver:
    def resolve_image(self, task_id: str) -> str:
        # 1. Task-specific override (config.yaml → task_overrides.{task_id})
        # 2. Task group pattern match (config.yaml → task_groups.{group}.pattern)
        # 3. Repository default (config.yaml → image)
```

### Repository Config (`config.yaml`)

Each repository has a `config.yaml` in `datasets/{repo}/`:

```yaml
repository: future-architect/vuls
language: go

# Default Docker image
image: ghcr.io/thecontextlab/swebench-pro-vuls:multi-agent

# Execution settings
workdir: /testbed
timeout_minutes: 45

# Agent configuration
agent:
  type: claude-code
  default_model: claude-sonnet-4-5-20250929

# MCP server for A/B testing (optional)
mcp:
  url: https://your-mcp-server.example.com/mcp

# Task groups for image routing (optional)
task_groups:
  python39_legacy:
    image: ghcr.io/thecontextlab/swebench-pro-ansible:multi-agent
    pattern: "ansible__ansible-.*-v(ba6da65a|1055803c)"
    python_version: "3.9"

# Task-specific overrides (optional)
task_overrides:
  "task-id-here":
    image: ghcr.io/thecontextlab/swebench-pro-custom:latest
```

## Multi-Agent Architecture

### BaseAgentAdapter

All agent integrations extend `BaseAgentAdapter` in `datasets/common/base_agent_adapter.py`:

```python
class BaseAgentAdapter(ABC):
    @abstractmethod
    def initialize_client(self) -> Any: ...
    @abstractmethod
    def format_tools(self) -> Any: ...
    @abstractmethod
    def call_agent(self, messages, tools) -> Tuple[str, Dict]: ...
    @abstractmethod
    def run(self) -> Dict: ...

    # Provided methods:
    def read_file(self, path) -> str: ...
    def write_file(self, path, content) -> str: ...
    def edit_file(self, path, old, new) -> str: ...
    def run_bash(self, command, timeout=120) -> str: ...
    def execute_tool(self, tool_name, args) -> str: ...
    def track_tool_usage(self, tool_name): ...
    def get_metrics(self) -> Dict: ...
```

The base class provides common file operations, bash execution, tool tracking, and metrics collection. Specific adapters focus on API integration.

### Agent Wrappers

Each agent has a per-repository wrapper script:

| Agent | Script | CLI Tool | Output Format | Permission Mode |
|-------|--------|----------|---------------|-----------------|
| Claude | `run_claude.py` | `claude` | `stream-json` (JSONL) | `acceptEdits` |
| Codex | `run_codex.py` | `codex` | JSONL events | `full-auto` |
| Gemini | `run_gemini.py` | `gemini` | `stream-json` (JSONL) | `auto-approve` |

#### Claude Integration

```python
cmd = [
    "claude", "--print",
    "--permission-mode", "acceptEdits",
    "--allowedTools", "Bash,Edit,Read,Write,Grep,Glob,WebFetch,Task,TodoWrite",
    "-p", instruction,
    "--output-format", "stream-json",
    "--verbose",
    "--model", model,
]
```

Claude produces JSONL output with `system`, `assistant`, and `result` event types. The `result` event contains aggregate token usage and cost.

#### Codex Integration

Codex produces JSONL with event types:
- `thread.started` — session start
- `turn.started` / `turn.completed` — turn lifecycle with usage stats
- `item.completed` — tool calls (`command_execution`, `file_change`, `mcp_tool_call`)
- `error` — rate limits and failures

#### Gemini Integration

Gemini produces stream-json with event types:
- `init` — session start with model name
- `tool_result` — individual tool call results
- `result` — final stats (tokens, duration, tool counts)

## MCP Integration

### Configuration

MCP servers are configured per-repository in `config.yaml`:

```yaml
mcp:
  url: https://your-mcp-server.example.com/mcp
```

When `enable_mcp=true`, the workflow passes the MCP URL to the agent wrapper. The wrapper constructs an MCP config:

```json
{
  "mcpServers": {
    "code-search": {
      "type": "http",
      "url": "https://your-mcp-server.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_TOKEN}"
      }
    }
  }
}
```

### A/B Testing

MCP integration enables controlled A/B experiments:

- **Baseline** (`enable_mcp=false`): Agent uses only built-in tools (Bash, Read, Edit, Write, Grep, Glob)
- **Treatment** (`enable_mcp=true`): Agent also gets MCP tools (e.g., `searchCode`, `searchSymbols`, `getCode`)

Both runs are tracked with identical metrics, enabling comparison of:
- Resolution rates
- Token usage and cost
- Tool call patterns
- Duration

### Tool Tracking

All tool calls (built-in and MCP) are captured in `result.json`:

```json
{
  "tool_usage": {
    "all_tools": {"Bash": 20, "Read": 15, "Edit": 3, "mcp__server__searchCode": 5},
    "total_tool_calls": 43,
    "mcp_tools": {
      "total_calls": 5,
      "tools": {"mcp__server__searchCode": 3, "mcp__server__getCode": 2},
      "queries": [...]
    }
  }
}
```

## Test Framework Support

The platform supports 7 test frameworks across 11 repositories:

| Framework | Repositories | Parser | Output Pattern |
|-----------|-------------|--------|----------------|
| pytest | ansible, openlibrary, qutebrowser | `_parse_pytest()` | `test.py::Test::method PASSED/FAILED` |
| go test | vuls, flipt, navidrome | `_parse_go()` | `--- PASS/FAIL: TestName (0.00s)` |
| go test (custom) | teleport | `_parse_go_custom()` | Standard + `EXPECTED: Test function ... does not exist` |
| jest | element-web | `_parse_jest()` | `PASS/FAIL path/to/test.tsx` + `✓/✕ description` |
| jest (workspace) | webclients | `_parse_jest_workspace()` | `Running test:` / `Test execution completed/failed for` |
| mocha | NodeBB | `_parse_mocha()` | JSON reporter with `tests[].err` |
| custom | tutanota | `_parse_custom_tutanota()` | `All N assertions passed` / `N out of M failed` |

Each parser is implemented in `extract_metrics.py` and handles framework-specific output parsing to determine per-test pass/fail outcomes. See [ANALYTICS.md](ANALYTICS.md) for parser details.

## Known Limitations

| Limitation | Impact | Tracking |
|------------|--------|----------|
| MCP is Claude-only | Codex and Gemini wrappers have zero MCP code — A/B testing is limited to Claude | [ADR-012](https://github.com/thecontextlab/swebench-pro-runner/issues/27) |
| `MAX_TURNS` not implemented | Workflow accepts `max_turns` input and passes `MAX_TURNS` env var, but no agent wrapper reads it | [ADR-006](https://github.com/thecontextlab/swebench-pro-runner/issues/21) |
| 33 duplicate agent wrappers | Each repo has near-identical `run_claude.py`, `run_codex.py`, `run_gemini.py` (11 repos x 3 agents) | [ADR-007](https://github.com/thecontextlab/swebench-pro-runner/issues/22) |
| MCP server name hardcoded | Always `"mcp-server"` — cannot distinguish providers in analytics | [ADR-002](https://github.com/thecontextlab/swebench-pro-runner/issues/17) |
| Dead config fields | `token_secret_name`, `max_concurrent`, and `mcp.description` are parsed but never consumed | [ADR-003](https://github.com/thecontextlab/swebench-pro-runner/issues/18) |
| Agent CLIs coupled to repo images | All 22 images include Node.js 20 + 3 agent CLIs; updating a CLI requires rebuilding all images | [ADR-013](https://github.com/thecontextlab/swebench-pro-runner/issues/28) |

### Architectural divergence from upstream

The upstream [SWE-bench_Pro-os](https://github.com/scaleapi/SWE-bench_Pro-os) uses 1,462 per-task Dockerfiles (base + instance per task) pre-built on Docker Hub. We use 22 repo-level images with per-task `setup.sh` scripts — a hybrid approach driven by multi-agent CLI requirements and infrastructure failure reduction. A potential future direction is a sidecar pattern that decouples agent CLIs from repo images entirely. See [DOCKER-IMAGES.md](DOCKER-IMAGES.md#design-decisions) for the full rationale.

For the full configuration surface area (all 6 levels), see [CONFIGURATION.md](CONFIGURATION.md). For MCP server onboarding, see [MCP-ONBOARDING.md](MCP-ONBOARDING.md).

## Data Flow

```
task.yaml ──┐
             ├──▶ swebench-eval.yml ──▶ Docker container ──┐
config.yaml ─┘                                              │
                                                            ▼
                                                     ┌─────────────┐
                                                     │ agent.log   │──┐
                                                     │ verify.log  │  ├──▶ extract_metrics.py ──▶ result.json
                                                     │ changes.patch│──┘
                                                     └─────────────┘
                                                            │
                                                            ▼
                                                     GitHub Actions
                                                      Artifact Upload
                                                            │
                                                            ▼
                                                     Orchestration Scripts
                                                     (download, validate,
                                                      audit, report)
```

1. **Task YAML** + **config.yaml** define what to run and how
2. **Workflow** orchestrates the Docker container execution
3. **Container** produces raw artifacts (agent.log, verification.log, changes.patch)
4. **extract_metrics.py** parses all artifacts into structured `result.json`
5. **Orchestration scripts** download, validate, and analyze results at scale
