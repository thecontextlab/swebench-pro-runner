# Glossary

Quick reference for terms used throughout this project. If you're new to AI agent evaluations, GitHub Actions, or Docker — start here.

---

## Core Concepts

### SWE-bench
**S**oft**w**are **E**ngineering Benchmark. A benchmark that tests whether AI agents can fix real bugs in real codebases. Created by Princeton researchers ([paper](https://arxiv.org/abs/2310.06770)). SWE-bench Pro is Scale AI's more challenging extension with longer, multi-file tasks ([paper](https://arxiv.org/abs/2509.16941)).

### F2P (Fail-to-Pass)
Tests that **must fail before** the agent runs and **must pass after**. This proves the agent actually fixed the bug. If a test passes before the agent even starts, the task setup is invalid.

### P2P (Pass-to-Pass)
Tests that **must pass both before and after** the agent runs. This catches regressions — the agent's fix shouldn't break unrelated functionality.

### Resolved
A task is "resolved" when **all F2P tests pass AND all P2P tests still pass**. Both conditions must be true. Partial credit is not given.

### Pre-Verification / Post-Verification
Tests run twice: **pre** (before the agent runs) to confirm the starting state is correct, and **post** (after the agent runs) to check if the fix worked.

### Base Commit
The git commit hash that represents the state of the code **before the bug was fixed**. The repo is reset to this commit so the agent has to find and apply the fix itself.

### Patch
A text file showing the differences between two versions of code (created by `git diff`). In this project, `changes.patch` captures everything the agent modified.

### Best-of-N
Running the same task multiple times (N runs) and selecting the best result. Used because AI agents are non-deterministic — they might succeed on attempt 3 even if they failed on attempts 1 and 2. The `assemble_best_of_n.py` script handles this.

---

## AI / LLM Terms

### Token
The basic unit that LLMs process. Roughly 4 characters or 0.75 words of English text. You pay per token — both for what you send to the model (**input tokens**) and what it generates back (**output tokens**).

### Cache Tokens
Tokens from previous turns that the model can reuse without reprocessing. **Cache read** tokens are cheaper than fresh input tokens. Cache reduces cost on multi-turn conversations.

### TPM (Tokens Per Minute)
Rate limit imposed by API providers. If you exceed your TPM allowance, requests get rejected with a `rate_limit_error`. New API accounts typically have lower TPM limits.

### MCP (Model Context Protocol)
An open standard ([modelcontextprotocol.io](https://modelcontextprotocol.io)) that lets AI agents use external tools (like code search, symbol lookup, etc.) via a standardized API. In this project, MCP is used for A/B testing — comparing agent performance with and without access to code intelligence tools.

### A/B Testing
Comparing two conditions to measure impact. Here: running the same task with MCP tools enabled vs. disabled, to see if external tools improve agent performance.

### Agent Wrapper
A Python script (`run_claude.py`, `run_codex.py`, `run_gemini.py`) that invokes the AI agent's CLI tool with the right flags, captures output, and handles logging. Each repository has its own set of wrappers.

---

## Infrastructure Terms

### GitHub Actions
GitHub's built-in CI/CD platform. Runs automated workflows (defined in `.yml` files) in cloud VMs. In this project, each evaluation task runs as a separate GitHub Actions workflow.

### workflow_dispatch
A GitHub Actions trigger type that lets you start a workflow manually (via the GitHub UI or `gh` CLI) with custom inputs. Both our workflows use this — evaluations are never triggered automatically by pushes or PRs.

### Artifact (GitHub Actions)
Files uploaded from a workflow run that you can download later. Our workflows upload `result.json`, `agent.log`, `changes.patch`, and verification logs as artifacts with 90-day retention.

### gh CLI
GitHub's official command-line tool ([cli.github.com](https://cli.github.com)). Used to dispatch workflows, monitor runs, and download artifacts. Must be installed and authenticated (`gh auth login`) before use.

### GHCR (GitHub Container Registry)
GitHub's Docker image hosting service at `ghcr.io`. Our pre-built Docker images live here (e.g., `ghcr.io/thecontextlab/swebench-pro-vuls:multi-agent`).

### Docker Image vs. Container
A Docker **image** is a snapshot of an environment (OS, tools, dependencies). A Docker **container** is a running instance of that image. Our images are pre-built with all dependencies; the workflow creates a temporary container from the image for each evaluation run.

---

## File Formats

### YAML
A human-readable data format used for configuration files (`.yaml`). Indentation matters. Used for task definitions and repository configs in this project.

### JSONL (JSON Lines)
A text format where each line is a separate JSON object. Used for streaming agent output — each event (tool call, response, error) is one line. Makes it easy to process logs line-by-line.

### Parquet
A columnar data format used by the Hugging Face dataset. More efficient than CSV for large datasets. You can load it with `pandas` or the `datasets` library.

---

## Project-Specific Terms

### Task
A single evaluation problem. Defined by a `.yaml` file containing the bug description, the base commit, and which tests must change state (F2P/P2P).

### Task ID / Slug
The unique identifier for a task, formatted as `{github_org}__{repo_name}-{commit_hash}`. Example: `future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c`.

### Task Group
A set of tasks that share configuration (e.g., the same Docker image or Python version). Defined by regex patterns in `config.yaml`. Example: all Ansible tasks requiring Python 3.11.

### Run Script (`run_script.sh`)
The shell script that executes tests for a specific task. Framework-specific — uses `go test -run` for Go, `pytest -k` for Python, `jest` for TypeScript, etc.

### Setup Script (`setup.sh`)
The shell script that provisions the environment inside the Docker container (installs dependencies, activates virtualenvs, etc.) before tests run.

### `before_repo_set_cmd`
Git commands executed at the start of each evaluation to set the repository to the correct state: reset to the base commit, then cherry-pick just the test files so the bug is present but the tests exist.

### Config Hierarchy
The three-level priority system for resolving Docker images and other settings: **task-specific override** > **task group pattern** > **repository default**. Implemented in `config_loader.py`. For the full 6-level configuration surface area, see [CONFIGURATION.md](CONFIGURATION.md).

### ADR (Architecture Decision Record)
A lightweight document capturing an architectural decision: the context, the decision, and its consequences. This project tracks ADRs as GitHub issues indexed at [docs/adr/README.md](adr/README.md).

### Treatment Run
An evaluation run with MCP enabled (`enable_mcp=true`). The agent gets access to MCP tools in addition to its built-in tools. Compared against a baseline run to measure MCP impact.

### Baseline Run
An evaluation run with MCP disabled (`enable_mcp=false`). The agent uses only its built-in tools (Bash, Read, Edit, Write, Grep, Glob). Serves as the control condition for A/B testing.

### Tool Allowlisting
Restricting which tools an agent can use during an evaluation. For Claude, this is controlled via the `--allowedTools` flag. Per-task allowlisting is tracked in [ADR-009](https://github.com/thecontextlab/swebench-pro-runner/issues/24).

### Task Group Pattern
A regex pattern in `config.yaml` that matches task IDs to route them to specific Docker images or settings. For example, `"ansible__ansible-.*-v(ba6da65a)"` routes matching Ansible tasks to a Python 3.9 image.

### MCP Server Name
The identifier used as the key in the `mcpServers` configuration dictionary. Currently hardcoded as `"mcp-server"` in all agent wrappers. Tool calls appear as `mcp__<server_name>__<tool>` in logs. Making this configurable is tracked in [ADR-002](https://github.com/thecontextlab/swebench-pro-runner/issues/17).

### Sidecar Pattern
An architectural pattern where the agent CLI runs in a dedicated container alongside the repo container, sharing `/testbed` and `/results` via a mounted volume. This decouples agent CLI versions from repo environment setup. Evaluated in [ADR-013](https://github.com/thecontextlab/swebench-pro-runner/issues/28).

### Hybrid Image Strategy
The approach used by this platform: 22 repo-level Docker images with prebaked dependencies + 731 per-task `setup.sh` scripts for runtime provisioning. Contrasts with the upstream SWE-bench_Pro-os approach of 1,462 per-task Dockerfiles. See [DOCKER-IMAGES.md](DOCKER-IMAGES.md#design-decisions).

### pypi-timemachine
A tool used by the upstream SWE-bench_Pro-os project (and referenced in our setup.sh scripts) that mocks PyPI to return packages as they existed on a specific date. Ensures dependency installation matches the historical state of the task's codebase.
