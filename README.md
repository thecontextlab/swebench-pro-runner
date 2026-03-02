# SWE-bench Pro Runner

An open-source evaluation platform for testing AI coding agents on real-world software engineering tasks. SWE-bench Pro Runner provides 742 curated tasks across 11 production repositories, with full orchestration tooling to launch evaluations, track results, and generate analytics reports.

The platform runs evaluations in Docker containers via GitHub Actions: an AI agent receives a task instruction and a failing test, then must fix the code so the test passes — while ensuring existing tests don't regress.

## Quick Start

1. **Fork this repository** to your GitHub account.

2. **Set up secrets** in your fork's Settings → Secrets → Actions:
   ```
   ANTHROPIC_API_KEY    # For Claude agents
   OPENAI_API_KEY       # For Codex agents
   GEMINI_API_KEY       # For Gemini agents
   ```

3. **Run your first evaluation:**
   ```bash
   gh workflow run swebench-eval.yml \
     -f repo=vuls \
     -f task="future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c" \
     -f agent=claude \
     -f model="claude-sonnet-4-5-20250929" \
     -f enable_mcp=false
   ```

4. **Monitor the run:**
   ```bash
   gh run list --workflow=swebench-eval.yml --limit=5
   ```

5. **Download results:**
   ```bash
   gh run download <run-id> --name=swebench-result-*
   ```

## Repository Structure

```
swebench-pro-runner/
├── .github/workflows/
│   ├── swebench-eval.yml         # Main evaluation workflow
│   └── regression-test.yml       # Pass-to-pass regression testing
├── datasets/
│   ├── common/
│   │   ├── config_loader.py      # Task-specific configuration resolver
│   │   └── base_agent_adapter.py # Multi-agent base class
│   ├── vuls/                     # Per-repo dataset
│   │   ├── config.yaml           # Docker image, timeout, MCP config
│   │   ├── run_claude.py         # Claude Code agent wrapper
│   │   ├── run_codex.py          # OpenAI Codex agent wrapper
│   │   ├── run_gemini.py         # Gemini CLI agent wrapper
│   │   ├── extract_metrics.py    # Metrics extraction (all frameworks)
│   │   └── tasks/                # Task definitions
│   │       ├── {task_id}.yaml        # Task instruction + test spec
│   │       ├── {task_id}.setup.sh    # Environment provisioning
│   │       └── {task_id}.run_script.sh # Test execution script
│   ├── ansible/
│   ├── flipt/
│   └── ...                       # 11 repositories total
├── scripts/
│   └── eval-orchestration/       # CLI tools for the full eval lifecycle
│       ├── launch_tasks.py       # Dispatch tasks to GitHub Actions
│       ├── monitor_runs.py       # Track run status
│       ├── download_artifacts.py # Download results
│       ├── validate_artifacts.py # Check artifact integrity
│       ├── extract_failing_tasks.py  # Find tasks to rerun
│       ├── assemble_best_of_n.py     # Best-of-N selection
│       ├── generate_report.py    # Markdown + CSV reports
│       ├── audit_artifacts.py    # Ground-truth verification parsing
│       └── _utils.py             # Shared utilities
└── docs/
    ├── ARCHITECTURE.md           # Workflow pipeline and container execution
    ├── TASK-SCHEMA.md            # Task YAML format and test patterns
    ├── DOCKER-IMAGES.md          # Image catalog and build process
    ├── EVAL-ORCHESTRATION.md     # End-to-end lifecycle guide
    └── ANALYTICS.md              # result.json schema and metrics
```

## Dataset Summary

| Repository | Language | Tasks | Test Framework | Complexity |
|------------|----------|------:|----------------|------------|
| [ansible](https://github.com/ansible/ansible) | Python | 97 | pytest | Very High |
| [openlibrary](https://github.com/internetarchive/openlibrary) | Python | 92 | pytest | High |
| [flipt](https://github.com/flipt-io/flipt) | Go | 86 | go test | Medium |
| [qutebrowser](https://github.com/qutebrowser/qutebrowser) | Python | 80 | pytest | High |
| [teleport](https://github.com/gravitational/teleport) | Go | 77 | go test (custom) | Very High |
| [webclients](https://github.com/protonmail/WebClients) | TypeScript | 66 | jest (workspace) | Very High |
| [vuls](https://github.com/future-architect/vuls) | Go | 63 | go test | Medium |
| [navidrome](https://github.com/navidrome/navidrome) | Go | 58 | go test | Medium |
| [element-web](https://github.com/element-hq/element-web) | TypeScript | 57 | jest | High |
| [NodeBB](https://github.com/NodeBB/NodeBB) | JavaScript | 45 | mocha | Medium |
| [tutanota](https://github.com/tutao/tutanota) | TypeScript | 21 | custom | High |
| **Total** | | **742** | | |

## Supported Agents

| Agent | Models | API Key Secret |
|-------|--------|----------------|
| Claude | `claude-sonnet-4-5-20250929`, `claude-opus-4-6`, `claude-opus-4-5-20251101`, `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| Codex | `gpt-5.3-codex`, `gpt-5.2-codex`, `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| Gemini | `gemini-3-pro-preview`, `gemini-1.5-pro`, `gemini-2.0-flash-exp` | `GEMINI_API_KEY` |

Each agent has a dedicated wrapper (`run_claude.py`, `run_codex.py`, `run_gemini.py`) that handles CLI invocation, permission modes, output format, and log capture.

## Evaluation Lifecycle

```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐    ┌────────┐
│ Launch   │───▶│ Monitor │───▶│ Download │───▶│ Validate │───▶│ Audit  │───▶│ Report │
│ Tasks    │    │ Runs    │    │ Artifacts│    │ Results  │    │ Ground │    │ Generate│
│          │    │         │    │          │    │          │    │ Truth  │    │         │
└─────────┘    └─────────┘    └──────────┘    └──────────┘    └────────┘    └────────┘
     │                                              │
     │              ┌──────────┐    ┌──────────┐    │
     └──────────────│ Extract  │◀───│ Assemble │◀───┘
        (rerun)     │ Failures │    │ Best-of-N│
                    └──────────┘    └──────────┘
```

Each step has a dedicated CLI tool in `scripts/eval-orchestration/`. See [docs/EVAL-ORCHESTRATION.md](docs/EVAL-ORCHESTRATION.md) for the full guide.

## Key Concepts

### Fail-to-Pass (F2P) Testing

Every task specifies tests that **must fail before** the agent runs and **must pass after**. This ensures the agent actually fixed the issue rather than the tests being trivially passing.

### Pass-to-Pass (P2P) Regression Testing

Tasks can optionally specify tests that **must pass both before and after** the agent runs. This catches regressions — the agent's fix shouldn't break existing functionality.

### Pre/Post Verification

The workflow runs verification tests twice:
- **Pre-verification**: Confirms F2P tests fail (validates the task is legitimate)
- **Post-verification**: Checks if the agent's changes made F2P tests pass

A task is **resolved** when all F2P tests pass AND all P2P tests still pass (no regression).

### MCP Support

The platform supports [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers for A/B testing. When `enable_mcp=true`, the agent gets access to additional tools from a configured MCP server. MCP server URLs and authentication are configured per-repository in `config.yaml`.

This enables controlled experiments comparing agent performance with and without access to external code intelligence tools.

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Workflow pipeline, container execution, multi-agent, MCP integration |
| [TASK-SCHEMA.md](docs/TASK-SCHEMA.md) | Task YAML schema, setup scripts, test execution patterns |
| [DOCKER-IMAGES.md](docs/DOCKER-IMAGES.md) | Image catalog, build process, adding new repositories |
| [EVAL-ORCHESTRATION.md](docs/EVAL-ORCHESTRATION.md) | Full lifecycle: launch → monitor → download → validate → report |
| [ANALYTICS.md](docs/ANALYTICS.md) | result.json schema, metrics extraction, cost models |

## Contributing

Contributions are welcome. The most impactful ways to contribute:

1. **Add new tasks** — Create task YAMLs for existing or new repositories. See [TASK-SCHEMA.md](docs/TASK-SCHEMA.md).
2. **Add new repositories** — Expand the dataset with new codebases and languages. See [DOCKER-IMAGES.md](docs/DOCKER-IMAGES.md).
3. **Add agent integrations** — Implement new agent adapters using `BaseAgentAdapter`. See [ARCHITECTURE.md](docs/ARCHITECTURE.md).
4. **Improve analytics** — Enhance metrics extraction, add new report formats. See [ANALYTICS.md](docs/ANALYTICS.md).
5. **Fix task definitions** — Improve setup scripts, test commands, or instructions.

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
