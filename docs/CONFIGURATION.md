# Configuration Reference

This document describes the full configuration surface area of the SWE-bench Pro Runner platform. It is aimed at teams who need to understand every knob that affects evaluation behavior — from workflow inputs down to container environment variables.

> **Resolves [ADR-005](adr/README.md)** — see [#20](https://github.com/thecontextlab/swebench-pro-runner/issues/20).

## Configuration Hierarchy

Configuration resolves through 6 levels. Higher levels override lower levels where applicable.

```
Level 1: Workflow Inputs          (user-provided at dispatch time)
Level 2: GitHub Secrets           (repository-level credentials)
Level 3: config.yaml — Defaults   (per-repo base settings)
Level 4: config.yaml — Task Groups (regex pattern matching)
Level 5: config.yaml — Task Overrides (exact task_id match)
Level 6: Container Env Vars       (runtime values inside Docker)
```

---

## Level 1: Workflow Inputs

These are provided when dispatching `swebench-eval.yml` via `gh workflow run` or the GitHub Actions UI.

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `repo` | choice | *(required)* | Target repository (11 options) |
| `task` | string | *(required)* | Full task ID (e.g., `future-architect__vuls-014413...`) |
| `agent` | choice | `claude` | Agent to run: `claude`, `codex`, or `gemini` |
| `model` | string | `claude-sonnet-4-5-20250929` | Model identifier passed to the agent CLI |
| `enable_mcp` | boolean | `false` | Enable MCP server for A/B testing |
| `anthropic_api_key` | string | *(empty)* | Override Anthropic API key (falls back to secret) |
| `openai_api_key` | string | *(empty)* | Override OpenAI API key (falls back to secret) |
| `gemini_api_key` | string | *(empty)* | Override Gemini API key (falls back to secret) |
| `timeout_minutes` | number | `60` | Total job timeout in minutes |
| `agent_timeout_minutes` | number | `45` | Agent step timeout in minutes |
| `max_turns` | number | `0` | Maximum agent turns (0 = unlimited) |

> **Known issue:** `max_turns` is passed to the container as `MAX_TURNS` but no agent wrapper reads it. See [ADR-006](https://github.com/thecontextlab/swebench-pro-runner/issues/21).

---

## Level 2: GitHub Secrets

Repository-level secrets configured in Settings → Secrets and variables → Actions.

| Secret | Used By | Description |
|--------|---------|-------------|
| `ANTHROPIC_API_KEY` | Claude agent | Anthropic API key for Claude Code CLI |
| `OPENAI_API_KEY` | Codex agent | OpenAI API key for Codex CLI |
| `GEMINI_API_KEY` | Gemini agent | Google API key for Gemini CLI |
| `MCP_TOKEN` | Claude agent (MCP) | Bearer token for MCP server authentication |

Workflow input API keys (`anthropic_api_key`, etc.) override these secrets when provided.

---

## Level 3: config.yaml — Repository Defaults

Each repository has a `config.yaml` at `datasets/{repo}/config.yaml`. These are the base settings that apply to all tasks in that repo.

```yaml
repository: future-architect/vuls
language: go

image: ghcr.io/thecontextlab/swebench-pro-vuls:multi-agent

workdir: /testbed
timeout_minutes: 45
max_concurrent: 5

agent:
  type: claude-code
  default_model: claude-sonnet-4-5-20250929

mcp:
  url: https://your-mcp-server.example.com/mcp
  description: "MCP server - indexed vuls codebase"

tasks:
  count: 62
  pattern: future-architect__vuls-*
```

### Field Reference

| Field | Used | Description |
|-------|------|-------------|
| `repository` | Yes | GitHub org/repo for `git clone` |
| `language` | Yes | Primary language (go, python, typescript, javascript) |
| `image` | Yes | Default Docker image (GHCR path + tag) |
| `workdir` | Yes | Working directory inside the container |
| `timeout_minutes` | Yes | Per-config timeout (overridden by workflow input) |
| `max_concurrent` | **No** | Parsed but never consumed by any code |
| `agent.type` | Yes | Agent type identifier |
| `agent.default_model` | Yes | Fallback model when workflow input is empty |
| `mcp.url` | Yes | MCP server HTTP endpoint |
| `mcp.description` | **No** | Metadata only — not used by code |
| `mcp.token_secret_name` | **No** | Present only in ansible config, never read by code. See [ADR-003](https://github.com/thecontextlab/swebench-pro-runner/issues/18) |
| `tasks.count` | Yes | Task count for orchestration scripts |
| `tasks.pattern` | Yes | Glob pattern for task ID matching |

---

## Level 4: config.yaml — Task Groups

Task groups use regex patterns to route groups of tasks to specific Docker images or settings. Defined under `task_groups` in config.yaml.

```yaml
task_groups:
  python39_legacy:
    image: ghcr.io/thecontextlab/swebench-pro-ansible:multi-agent
    pattern: "ansible__ansible-.*-v(ba6da65a|1055803c|...)"
    python_version: "3.9"

  python311_modern:
    image: ghcr.io/thecontextlab/swebench-pro-ansible-python311:multi-agent
    pattern: "ansible__ansible-.*-v(abc12345|def67890|...)"
    python_version: "3.11"
```

### Resolvable Fields

Task groups can override these fields:

| Field | Description |
|-------|-------------|
| `image` | Docker image for matching tasks |
| `python_version` | Python version (used in setup.sh) |
| `timemachine_date` | Date constraint for pip installs |

Resolution is implemented by `TaskImageResolver` in `datasets/common/config_loader.py`. The first matching pattern wins (patterns are tested in definition order).

---

## Level 5: config.yaml — Task Overrides

Exact task ID overrides. Highest priority in the config.yaml hierarchy.

```yaml
task_overrides:
  "future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c":
    image: ghcr.io/thecontextlab/swebench-pro-vuls-special:multi-agent
    timemachine_date: "2024-01-15"
```

Same resolvable fields as task groups: `image`, `python_version`, `timemachine_date`.

---

## Level 6: Container Environment Variables

These environment variables are set inside the Docker container at runtime by the workflow.

| Variable | Source | Description |
|----------|--------|-------------|
| `MODEL` | Workflow input `model` | Model identifier for the agent CLI |
| `MCP_URL` | config.yaml `mcp.url` | MCP server endpoint |
| `MCP_TOKEN` | `secrets.MCP_TOKEN` | Bearer token for MCP auth |
| `MCP_CONFIG` | config_loader.py | Legacy MCP config (always empty string) |
| `MAX_TURNS` | Workflow input `max_turns` | Agent turn limit (**not implemented** — see [ADR-006](https://github.com/thecontextlab/swebench-pro-runner/issues/21)) |
| `TASK_ID` | Workflow input `task` | Full task identifier |
| `ANTHROPIC_API_KEY` | Secret or workflow input | API key for Claude |
| `OPENAI_API_KEY` | Secret or workflow input | API key for Codex |
| `GEMINI_API_KEY` | Secret or workflow input | API key for Gemini |

---

## Agent Capability Comparison

Each agent CLI has different capabilities and permission models:

| Capability | Claude | Codex | Gemini |
|------------|--------|-------|--------|
| Permission mode | `acceptEdits` | `full-auto` | `auto-approve` |
| Output format | `stream-json` (JSONL) | JSONL events | `stream-json` (JSONL) |
| MCP support | Yes | No | No |
| Built-in tools | Bash, Edit, Read, Write, Grep, Glob, WebFetch, Task, TodoWrite | Full sandbox access | Bash, Edit, Read, Write, Grep, Glob |
| Model fallback | No | No | Yes (retries with `gemini-2.0-flash`) |
| Cost tracking | Via `result` event | Via `turn.completed` events | Via `result` event |
| Tool allowlisting | `--allowedTools` flag | N/A (sandbox) | N/A (auto-approve all) |

### Claude-specific MCP Behavior

When `enable_mcp=true`:
- MCP server config is written to `/tmp/mcp_config.json`
- `--mcp-config` flag is added to the `claude` CLI command
- `mcp__mcp-server` is appended to `--allowedTools`
- A runtime `CLAUDE.md` is written to `/testbed/` with MCP tool hints

### Codex and Gemini

Neither Codex nor Gemini wrappers have MCP integration. See [ADR-012](https://github.com/thecontextlab/swebench-pro-runner/issues/27) for planned work.

---

## config.yaml Full Schema

```yaml
# Required fields
repository: "org/repo"              # GitHub repository
language: "go"                      # go | python | typescript | javascript

# Docker image (required)
image: "ghcr.io/thecontextlab/swebench-pro-{repo}:{tag}"

# Execution settings
workdir: "/testbed"                 # Container working directory
timeout_minutes: 45                 # Config-level timeout

# Agent settings
agent:
  type: "claude-code"               # Agent type identifier
  default_model: "claude-sonnet-4-5-20250929"  # Fallback model

# MCP settings (optional)
mcp:
  url: ""                           # MCP server HTTP endpoint
  description: ""                   # Human-readable description (metadata only)
  # token_secret_name: ""           # DEAD — not used by code (ADR-003)

# Task metadata
tasks:
  count: 62                         # Number of tasks
  pattern: "org__repo-*"            # Task ID glob pattern

# DEAD FIELD — not consumed by any code
# max_concurrent: 5

# Task group routing (optional)
task_groups:
  group_name:
    image: "ghcr.io/..."           # Override Docker image
    pattern: "regex_pattern"        # Regex to match task IDs
    python_version: "3.11"          # Python version (optional)
    timemachine_date: "2024-01-15"  # Pip timemachine date (optional)

# Task-specific overrides (optional, highest priority)
task_overrides:
  "exact-task-id":
    image: "ghcr.io/..."           # Override Docker image
    python_version: "3.11"          # Python version (optional)
    timemachine_date: "2024-01-15"  # Pip timemachine date (optional)
```

---

## Known Gaps

| Gap | Description | Tracking |
|-----|-------------|----------|
| `MAX_TURNS` not implemented | Env var passed but never read by agents | [ADR-006](https://github.com/thecontextlab/swebench-pro-runner/issues/21) |
| `token_secret_name` dead | Field in ansible config, never consumed | [ADR-003](https://github.com/thecontextlab/swebench-pro-runner/issues/18) |
| `max_concurrent` dead | Field in all configs, never consumed | — |
| `mcp.description` dead | Metadata field, never consumed | — |
| MCP is Claude-only | Codex/Gemini have no MCP code | [ADR-012](https://github.com/thecontextlab/swebench-pro-runner/issues/27) |
| 33 duplicate wrappers | Each repo has near-identical agent scripts | [ADR-007](https://github.com/thecontextlab/swebench-pro-runner/issues/22) |

## Related Documentation

- [MCP-ONBOARDING.md](MCP-ONBOARDING.md) — step-by-step guide for MCP server integration
- [ARCHITECTURE.md](ARCHITECTURE.md) — evaluation pipeline and system overview
- [DOCKER-IMAGES.md](DOCKER-IMAGES.md) — image catalog and build process
- [ANALYTICS.md](ANALYTICS.md) — result.json schema and metrics extraction
