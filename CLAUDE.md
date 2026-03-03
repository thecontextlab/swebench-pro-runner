# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SWE-bench Pro Runner is an evaluation platform for testing AI coding agents (Claude, Codex, Gemini) on 731 real-world software engineering tasks across 11 production repositories. Evaluations run in Docker containers via GitHub Actions: an agent receives a task instruction + failing test, fixes the code, then verification checks that fail-to-pass (F2P) tests now pass and pass-to-pass (P2P) tests don't regress.

Built on the [SWE-bench Pro](https://arxiv.org/abs/2509.16941) benchmark by Scale AI. The public dataset is at [ScaleAI/SWE-bench_Pro](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro) on Hugging Face, with source code at [scaleapi/SWE-bench_Pro-os](https://github.com/scaleapi/SWE-bench_Pro-os).

## Common Commands

### Launch a single evaluation
```bash
gh workflow run swebench-eval.yml \
  -f repo=vuls \
  -f task="future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c" \
  -f agent=claude \
  -f model="claude-sonnet-4-5-20250929" \
  -f enable_mcp=false
```

### Orchestration scripts (Python 3.9+, stdlib + pyyaml only)
```bash
python3 scripts/eval-orchestration/launch_tasks.py --repo vuls --agent claude
python3 scripts/eval-orchestration/monitor_runs.py --repo vuls
python3 scripts/eval-orchestration/download_artifacts.py --repo vuls --output-dir ./results
python3 scripts/eval-orchestration/validate_artifacts.py --dir ./results
python3 scripts/eval-orchestration/generate_report.py --dir ./results
```

### Validate a task YAML
```bash
python3 -c "import yaml; yaml.safe_load(open('datasets/vuls/tasks/TASK_ID.yaml'))"
```

## Architecture

### Evaluation Pipeline (GitHub Actions)
The workflow in `.github/workflows/swebench-eval.yml` runs a 10-step pipeline:
1. Load task YAML + resolve Docker image via `config_loader.py`
2. Clone repo to `/testbed` in container
3. Apply `before_repo_set_cmd` (git reset to base commit + cherry-pick test changes)
4. Run `setup.sh` to provision environment
5. **Pre-verify F2P** — confirm fail-to-pass tests fail initially
6. **Pre-verify P2P** — confirm pass-to-pass tests pass (baseline)
7. **Run agent** — execute `run_claude.py` / `run_codex.py` / `run_gemini.py`
8. Capture `git diff` as `changes.patch`
9. **Post-verify F2P** — check if agent's fix made tests pass
10. **Post-verify P2P** — check for regressions
11. `extract_metrics.py` parses logs into `result.json`

### Configuration Hierarchy (3 levels)
Implemented in `datasets/common/config_loader.py` (`TaskImageResolver`):
- **Task-specific overrides** (highest) — `task_overrides` in `config.yaml`
- **Task group patterns** — regex matching in `task_groups`
- **Repository defaults** (fallback) — top-level `image` in `config.yaml`

### Per-Repository Dataset Structure
```
datasets/{repo}/
├── config.yaml             # Docker image, timeout, MCP config, task groups
├── run_claude.py           # Claude Code CLI wrapper
├── run_codex.py            # OpenAI Codex CLI wrapper
├── run_gemini.py           # Gemini CLI wrapper
├── extract_metrics.py      # Parses JSONL agent logs + test output → result.json
└── tasks/
    ├── {task_id}.yaml      # Task definition (instruction, base_commit, F2P/P2P tests)
    ├── {task_id}.setup.sh  # Environment provisioning
    └── {task_id}.run_script.sh  # Test execution harness (framework-specific)
```

### Agent Adapter Pattern
`datasets/common/base_agent_adapter.py` defines `BaseAgentAdapter` (abstract base class) with:
- Tool execution: `read_file()`, `write_file()`, `edit_file()`, `run_bash()`
- JSONL logging via `log_interaction()`
- Metrics tracking (tokens, tool usage, cost, errors)

Each repo has three concrete wrappers that invoke the respective CLI tools in the Docker container.

### Orchestration Scripts
All in `scripts/eval-orchestration/` — Python 3.9+ using only stdlib + pyyaml. Shared utilities in `_utils.py` (org→repo mapping, test framework classification). The pipeline: launch → monitor → download → validate → extract failures → (rerun) → assemble best-of-N → audit → report.

### Container Filesystem
```
/testbed/           # Cloned repo (agent's working directory)
/results/           # Output: result.json, agent.log, changes.patch, verification logs
/instruction.txt    # Task instruction
/run_script.sh      # Test harness
/setup.sh           # Environment setup
/run_agent.py       # Agent wrapper (copied from datasets/{repo}/)
```

## Key Patterns

- **Test frameworks vary by repo**: pytest (Python repos), go test (Go repos), jest (TS repos), mocha (NodeBB). Each repo's `run_script.sh` handles framework-specific test selection (`-k` for pytest, `-run` for go test, etc.)
- **Agent wrappers are per-repo** — they differ slightly in permission modes, allowed tools, and MCP configuration but follow the same structure
- **`extract_metrics.py` handles all three agent log formats** (Claude JSONL, Codex JSONL, Gemini JSONL) — parsing differs per agent
- **Task resolution**: a task is "resolved" only when F2P tests pass AND P2P tests don't regress
- **MCP is optional**: controlled by `enable_mcp` flag for A/B testing; configured per-repo in `config.yaml`

## Cost and Safety Awareness

Every evaluation run costs real money in API fees. When working on this codebase:

- **Never run `launch_tasks.py` without `--dry-run` first** — it dispatches GitHub Actions workflows that consume API credits
- **`datasets/common/` files are shared** — changes to `config_loader.py` or `base_agent_adapter.py` affect all 11 repositories
- **Both workflow files must stay in sync** — the repo dropdown in `swebench-eval.yml` and `regression-test.yml` must list the same repos
- **Agent wrappers have no token/turn limits** — a stuck agent burns credits until the 45-minute timeout kills it
- **Model costs vary dramatically** — Claude Opus is ~10x more expensive than Haiku; always confirm model choice is intentional
- Approximate cost per task: Haiku ~$0.10, Sonnet ~$0.30, Opus ~$3.00

## Repositories Covered

| Repo | Language | Test Framework |
|------|----------|----------------|
| ansible, openlibrary, qutebrowser | Python | pytest |
| vuls, flipt, navidrome, teleport | Go | go test |
| element-web, webclients, tutanota | TypeScript | jest/custom |
| NodeBB | JavaScript | mocha |

## Additional Docs

- [docs/ONBOARDING.md](docs/ONBOARDING.md) — learning path for new contributors and their AI agents
- [docs/GLOSSARY.md](docs/GLOSSARY.md) — definitions of domain terms (F2P, P2P, MCP, JSONL, tokens, etc.)
