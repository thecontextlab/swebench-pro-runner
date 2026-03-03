# Contributing to SWE-bench Pro Runner

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

> **New here?** Start with [docs/ONBOARDING.md](docs/ONBOARDING.md) for a guided learning path, and [docs/GLOSSARY.md](docs/GLOSSARY.md) if you encounter unfamiliar terms.

## Things to Avoid

Before diving in, please read these carefully — some mistakes are expensive or hard to reverse:

1. **Do NOT run all 742 tasks at once.** Each task costs $0.15-$5.00+ in API fees. Start with a single task, then small batches. Always use `--dry-run` first with `launch_tasks.py`.
2. **Do NOT use expensive models for testing.** Start with `claude-haiku-4-5-20251001`, `gpt-4o-mini`, or `gemini-2.0-flash-exp` while learning. Claude Opus and GPT-5 cost 5-10x more.
3. **Do NOT commit API keys or secrets.** Use GitHub repository secrets (Settings → Secrets and variables → Actions). Never put keys in code, YAML, or `.env` files that get committed.
4. **Do NOT modify workflow YAML files without validation.** A syntax error in `swebench-eval.yml` breaks all evaluations. Validate with an online YAML linter or `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/swebench-eval.yml'))"`.
5. **Do NOT edit files in `datasets/common/` casually.** `base_agent_adapter.py` and `config_loader.py` are shared by all 11 repositories — changes propagate everywhere.
6. **Do NOT push directly to `main`.** Always create a feature branch and submit a pull request.
7. **Do NOT re-run failing tasks in a loop.** If tasks keep failing, the issue is likely the task definition or the model's capability — not a transient error. Use `assemble_best_of_n.py` for multi-attempt strategies instead.

## Good First Contributions

If you're new, start here. These tasks are low-risk and help you learn the codebase:

| Task | Difficulty | What You'll Learn |
|------|-----------|-------------------|
| **Validate all task YAML files** — run the YAML parser on every task file and report any that fail | Easy | Task structure, Python scripting |
| **Count actual tasks per repo** — verify the README table (742 total) matches the real file count | Easy | Repository layout, shell commands |
| **Follow the Quick Start and document friction** — run one task end-to-end, note where you got stuck | Easy | Full evaluation pipeline |
| **Add missing `difficulty` fields** — some task YAMLs lack the optional `difficulty` field | Easy | Task YAML schema |
| **Improve error messages** — find places in orchestration scripts where errors are unclear | Medium | Python, orchestration pipeline |
| **Add `--help` text** — ensure all scripts in `scripts/eval-orchestration/` have clear help output | Medium | Python argparse, script purposes |
| **Write a YAML schema validator** — create a script that checks required fields, not just syntax | Medium | Task schema, validation patterns |

## How to Contribute

### Reporting Issues

- Search existing issues before creating a new one
- Include reproduction steps, expected behavior, and actual behavior
- For task-specific issues, include the task ID and repository name

### Adding New Tasks

1. Create a task YAML file in `datasets/{repo}/tasks/{task_id}.yaml`
2. Create a corresponding `setup.sh` for environment provisioning
3. Create a `run_script.sh` for test execution
4. Verify the task works end-to-end with the evaluation workflow

See [docs/TASK-SCHEMA.md](docs/TASK-SCHEMA.md) for the full task specification.

### Adding New Repositories

1. Create `datasets/{repo}/` directory structure
2. Add `config.yaml` with Docker image and metadata
3. Copy `run_claude.py`, `run_codex.py`, `run_gemini.py`, and `extract_metrics.py` from an existing dataset
4. Build and push a Docker image to GHCR
5. Add the repository to the `options` list in **both** workflow files (`swebench-eval.yml` and `regression-test.yml`)

See [docs/DOCKER-IMAGES.md](docs/DOCKER-IMAGES.md) for image build instructions.

### Code Changes

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Test locally where possible (see Development Setup below)
5. Submit a pull request

### Pull Request Guidelines

- Keep PRs focused on a single change
- Include a clear description of what changed and why
- Update documentation if behavior changes
- Ensure workflow YAML is valid
- Mention which task IDs or repositories are affected

## Development Setup

```bash
# Clone the repo
git clone https://github.com/thecontextlab/swebench-pro-runner.git
cd swebench-pro-runner

# Install Python dependencies for orchestration scripts
pip install pyyaml

# Install GitHub CLI (needed for running evaluations)
# macOS: brew install gh
# Linux: see https://cli.github.com/
gh auth login

# Validate a task file (syntax only)
python3 -c "import yaml; yaml.safe_load(open('datasets/vuls/tasks/future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c.yaml'))"

# Preview a batch launch without executing (dry run)
python3 scripts/eval-orchestration/launch_tasks.py --task-file your_tasks.txt --dry-run
```

## Using AI Coding Agents to Contribute

This project has a `CLAUDE.md` file that gives [Claude Code](https://claude.ai/code) context about the codebase architecture, common commands, and key patterns. You can use Claude Code (or similar AI coding tools) to help with contributions:

**Good uses for AI agents:**
- Understanding the codebase ("How does `config_loader.py` resolve Docker images?")
- Writing task YAML files (the schema is well-documented and repetitive)
- Debugging failing setup or run scripts
- Writing orchestration script enhancements
- Generating reports from result data

**Use human judgment for:**
- Verifying that task definitions are correct (AI can write the YAML, but a human should verify the test names and base commit)
- Reviewing cost implications of changes to agent wrappers or workflow files
- Decisions about which models or configurations to use for evaluations

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
