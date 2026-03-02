# Contributing to SWE-bench Pro Runner

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

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
3. Copy `run_claude.py` and `extract_metrics.py` from an existing dataset
4. Build and push a Docker image to GHCR
5. Add the repository to workflow input options

See [docs/DOCKER-IMAGES.md](docs/DOCKER-IMAGES.md) for image build instructions.

### Code Changes

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Test locally where possible
5. Submit a pull request

### Pull Request Guidelines

- Keep PRs focused on a single change
- Include a clear description of what changed and why
- Update documentation if behavior changes
- Ensure workflow YAML is valid

## Development Setup

```bash
# Clone the repo
git clone https://github.com/thecontextlab/swebench-pro-runner.git
cd swebench-pro-runner

# Install Python dependencies for orchestration scripts
pip install pyyaml requests

# Validate task files
python3 -c "import yaml; yaml.safe_load(open('datasets/vuls/tasks/future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c.yaml'))"
```

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
