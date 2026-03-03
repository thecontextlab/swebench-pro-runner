# Evaluation Orchestration

The `scripts/eval-orchestration/` directory contains 10 Python scripts that cover the full evaluation lifecycle. All scripts use Python 3.9+ stdlib only (no pip install needed) and require the `gh` CLI for GitHub Actions interaction.

## Lifecycle Overview

```
Launch → Monitor → Download → Validate → Extract Failures → Rerun → Assemble → Report
  │         │          │          │              │              │         │         │
  ▼         ▼          ▼          ▼              ▼              ▼         ▼         ▼
launch   monitor   download   validate    extract_failing   launch   assemble  generate
_tasks   _runs     _artifacts _artifacts  _tasks            _tasks   _best_of  _report
.py      .py       .py        .py         .py               .py      _n.py     .py
```

Additional tools for deeper analysis:
- `audit_artifacts.py` — Ground-truth verification via task YAML cross-referencing
- `launch_regression_tests.py` — Dispatch P2P regression tests for resolved tasks
- `generate_regression_result.py` — Parse regression test results

## Shared Utilities (`_utils.py`)

Common functions used by all scripts:

| Function | Purpose |
|----------|---------|
| `get_repo_from_folder(folder)` | Extract repo name from folder like `codex-gpt52-{repo}-{hash}` |
| `get_hash_part(folder)` | Extract task hash identifier from folder name |
| `load_result(folder_path)` | Load `result.json` with error handling |
| `get_task_id(data)` | Get task ID from result.json (handles `task_id` and `task` keys) |
| `extract_metrics(data)` | Normalize metrics across Claude/Codex result.json formats |
| `scan_agent_log(log_path)` | Detect `rate_limit` and `turn.failed` in agent.log |
| `parse_display_title(title)` | Parse GHA displayTitle into repo/task/agent/mcp components |
| `index_artifact_dir(directory)` | Index artifact dir into `{hash_part: path}` mapping |
| `get_repo_from_task_id(task_id)` | Map `ansible__ansible-abc123` to repo name `ansible` |
| `get_framework_for_repo(repo)` | Return test framework name for a repo |
| `load_task_yaml(yaml_dir, task_id)` | Load fail_to_pass list from task YAML |
| `load_pass_to_pass(yaml_dir, task_id)` | Load pass_to_pass list from task YAML |

### Repository and Organization Mapping

```python
ORG_TO_REPO = {
    "ansible": "ansible",       "element-hq": "element-web",
    "flipt-io": "flipt",        "navidrome": "navidrome",
    "NodeBB": "NodeBB",          "internetarchive": "openlibrary",
    "qutebrowser": "qutebrowser", "gravitational": "teleport",
    "tutao": "tutanota",         "future-architect": "vuls",
    "protonmail": "webclients",
}
```

### Framework Classification

```python
PYTEST_REPOS = {"ansible", "openlibrary", "qutebrowser"}
GO_REPOS = {"vuls", "flipt", "navidrome"}
GO_CUSTOM_REPOS = {"teleport"}
JEST_REPOS = {"element-web"}
JEST_WORKSPACE_REPOS = {"webclients"}
MOCHA_REPOS = {"NodeBB"}
CUSTOM_REPOS = {"tutanota"}
```

## Script Reference

### `launch_tasks.py` — Task Launcher

Dispatches evaluation tasks to GitHub Actions with rate-limit-aware delays.

```bash
python3 launch_tasks.py \
  --task-file tasks.txt \
  --model "claude-sonnet-4-5-20250929" \
  --agent claude \
  --mcp false \
  --delay 120 \
  --log-file launch.log \
  --dry-run
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--task-file` | Yes | — | Path to pipe-delimited task file |
| `--model` | Yes | — | Model string (e.g., `claude-sonnet-4-5-20250929`) |
| `--agent` | Yes | — | Agent: `claude`, `codex`, `gemini` |
| `--mcp` | No | `false` | `true` or `false` |
| `--delay` | No | `5` | Seconds between launches |
| `--log-file` | No | — | Log file for resume support (skips already-launched tasks) |
| `--dry-run` | No | — | Print commands without executing |
| `--max-tasks` | No | `0` | Maximum tasks to launch (0 = unlimited) |
| `-y`, `--yes` | No | — | Skip confirmation prompt for large batches |

**Cost safety:** When launching more than 10 tasks, the script shows an estimated cost and asks for confirmation. Use `--yes` to skip this in automated pipelines. Use `--dry-run` to preview without executing.

A sample task file with 100 representative tasks is available at `datasets/sample-100-tasks.txt`.

**Task file format** (pipe-delimited, one per line):
```
ansible|ansible__ansible-12734fa21c08a0ce8c84e533abdc560db2eb1955
element-web|element-hq__element-web-4c6b0d35abc123
vuls|future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c
# Comments and empty lines are skipped
```

### `monitor_runs.py` — Run Monitor

Polls GitHub Actions for run status with per-repo breakdown.

```bash
# One-shot status
python3 monitor_runs.py --start-date 2026-02-21 --model claude-sonnet-4-5-20250929

# Watch mode
python3 monitor_runs.py --start-date 2026-02-21 --model claude-opus-4-6 \
  --watch --interval 60

# Filter by repo and agent
python3 monitor_runs.py --start-date 2026-02-21 --repo flipt --agent codex
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--start-date` | No | — | Filter runs from this date (YYYY-MM-DD) |
| `--model` | No | — | Filter by model string |
| `--agent` | No | — | Filter by agent name |
| `--mcp` | No | — | Filter by MCP flag |
| `--repo` | No | — | Filter by repository |
| `--watch` | No | — | Continuously poll until all complete |
| `--interval` | No | `60` | Poll interval in seconds |
| `--limit` | No | `200` | Max runs to fetch from API |

### `download_artifacts.py` — Artifact Downloader

Downloads evaluation artifacts from completed GitHub Actions runs. Idempotent — skips already-downloaded artifacts.

```bash
python3 download_artifacts.py \
  --start-date 2026-02-20 \
  --model "claude-sonnet-4-5-20250929" \
  --agent claude \
  --mcp false \
  --output-dir ./eval-claude-sonnet45 \
  --folder-prefix "claude-sonnet-4-5" \
  --limit 500
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--start-date` | No | — | Start date filter (YYYY-MM-DD) |
| `--end-date` | No | — | End date filter |
| `--model` | No | — | Model string filter |
| `--agent` | No | — | Agent name filter |
| `--mcp` | No | — | MCP flag filter |
| `--output-dir` | Yes | — | Download destination directory |
| `--folder-prefix` | No | — | Prefix for downloaded folder names |
| `--cache-file` | No | — | Cache GHA run list to avoid repeated API calls |
| `--limit` | No | `500` | Max runs to fetch from API |
| `--status` | No | `completed` | Run status filter (e.g., `completed`, `in_progress`) |
| `--conclusion` | No | `success` | Run conclusion filter (e.g., `success`, `failure`) |

### `validate_artifacts.py` — Artifact Validator

Checks artifact integrity across a downloaded directory.

```bash
python3 validate_artifacts.py --artifact-dir ./eval-claude-sonnet45

# Export JSON report
python3 validate_artifacts.py --artifact-dir ./eval-claude-sonnet45 --output-json report.json
```

**Checks performed:**
- `result.json` exists, is valid JSON, has required fields (`resolved`, `task`/`task_id`)
- `agent.log` exists and is non-trivial (>500 bytes)
- `pre_verification.log` exists
- `verification.log` exists
- Rate limiting detection in `agent.log`
- `turn.failed` event detection in `agent.log`
- Consistency: `result.json` resolved status matches verification.log outcome

### `extract_failing_tasks.py` — Failing Task Extractor

Identifies failed tasks for reruns. Supports multiple output formats.

```bash
# Launch-ready format (pipe directly to launch_tasks.py --task-file)
python3 extract_failing_tasks.py --artifact-dir ./eval-claude --format launch > rerun.txt

# Only rate-limited failures
python3 extract_failing_tasks.py --artifact-dir ./eval-claude \
  --rate-limited-only --format launch

# CSV with metrics for analysis
python3 extract_failing_tasks.py --artifact-dir ./eval-claude --format csv

# Exclude known broken tasks
python3 extract_failing_tasks.py --artifact-dir ./eval-claude \
  --exclude-broken abc123def456
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--artifact-dir` | Yes | — | Directory to scan |
| `--format` | No | `launch` | `launch` (pipe-delimited) or `csv` |
| `--rate-limited-only` | No | — | Only include rate-limited failures |
| `--include-all` | No | — | Include all failing tasks (ignore rate-limit filter) |
| `--exclude-broken` | No | — | Hash parts of broken tasks to skip |
| `--output` | No | stdout | Output file path |

### `assemble_best_of_n.py` — Best-of-N Assembly

Selects the best result per task across multiple evaluation runs.

```bash
# Best-of-two
python3 assemble_best_of_n.py \
  --sources "original=./run1,rerun=./run2" \
  --output-dir ./eval-bestof2

# Best-of-three with exclusions
python3 assemble_best_of_n.py \
  --sources "original=./run1,rerun=./run2,tier5=./run3" \
  --output-dir ./eval-bestof3 \
  --exclude-tasks abc123def456
```

**Selection rules** (per task, across all available runs):

1. `resolved=true` wins over `resolved=false`
2. If tied, prefer no rate limiting
3. If tied, prefer no `turn.failed`
4. If tied, prefer latest source (sources listed later have higher priority)

**Outputs:**
- Copies best artifacts to output directory
- `selection_metadata.csv` — which source was picked per task and why

### `generate_report.py` — Report Generator

Generates markdown report and CSV from evaluation artifacts.

```bash
# Markdown + CSV
python3 generate_report.py --artifact-dir ./eval-bestof3

# With baseline comparison
python3 generate_report.py --artifact-dir ./eval-bestof3 \
  --compare-dir ./eval-baseline \
  --compare-label "Claude sonnet-4-5"

# Exclude broken tasks from scoring
python3 generate_report.py --artifact-dir ./eval-bestof3 \
  --exclude-tasks abc123def456
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--artifact-dir` | Yes | — | Directory with artifacts |
| `--output-format` | No | `md,csv` | `md`, `csv`, or `md,csv` |
| `--output-dir` | No | artifact-dir | Where to write reports |
| `--exclude-tasks` | No | — | Broken task hash parts to exclude |
| `--compare-dir` | No | — | Baseline artifacts for comparison |
| `--compare-label` | No | — | Label for baseline in comparison tables |

**Report sections:**
- Summary (total tasks, resolved, pass rate, cost, duration)
- Per-repository breakdown
- Cost analysis (total, mean, median, p95)
- Token usage breakdown
- Tool usage analysis
- Comparison tables (if `--compare-dir` provided)

### `audit_artifacts.py` — Ground-Truth Auditor

Cross-references verification.log with task YAML fail_to_pass lists using framework-specific parsers. This is the authoritative way to determine task resolution — it doesn't trust `result.json`'s claimed status.

```bash
python3 audit_artifacts.py \
  --artifact-dir ./eval-bestof3 \
  --task-yaml-dir ../datasets \
  --output-csv audit-results.csv
```

**How it works:**
1. Loads `fail_to_pass` list from the task YAML
2. Determines the test framework from the repository
3. Parses `verification.log` with the framework-specific parser
4. Classifies each test as: TP (true positive), FP (false positive), FN (false negative), TN (true negative)
5. Compares audit result with `result.json`'s claimed `resolved` status

This catches cases where `result.json` is incorrect (e.g., exit code was 0 but tests actually failed, or vice versa).

### `launch_regression_tests.py` — Regression Test Launcher

Dispatches P2P regression tests for resolved tasks. Scans an artifact directory for resolved tasks with non-empty patches, then triggers `regression-test.yml` for each.

```bash
python3 launch_regression_tests.py \
  --artifact-dir ./eval-bestof3 \
  --task-yaml-dir datasets \
  --delay 30

# Dry run
python3 launch_regression_tests.py \
  --artifact-dir ./eval-bestof3 \
  --task-yaml-dir datasets \
  --dry-run
```

Only launches for tasks that have `pass_to_pass` tests defined in their YAML.

### `generate_regression_result.py` — Regression Result Generator

Parses regression test phase logs into structured `regression_result.json`. Runs as part of the `regression-test.yml` workflow.

**5-phase result parsing:**
1. F2P Pre-patch (should fail)
2. P2P Pre-patch (should pass)
3. F2P Post-patch (should pass)
4. P2P Post-patch (should pass — no regression)
5. Overall determination

## End-to-End Worked Example

Complete workflow for running a Claude Sonnet evaluation:

```bash
cd scripts/eval-orchestration/

# 1. Launch 100 tasks
python3 launch_tasks.py \
  --task-file ../../datasets/sample-100-tasks.txt \
  --model claude-sonnet-4-5-20250929 \
  --agent claude \
  --mcp false \
  --delay 120 \
  --log-file sonnet45-launch.log

# 2. Monitor until all complete
python3 monitor_runs.py \
  --start-date 2026-03-01 \
  --model claude-sonnet-4-5-20250929 \
  --watch --interval 120

# 3. Download completed artifacts
python3 download_artifacts.py \
  --start-date 2026-03-01 \
  --model claude-sonnet-4-5-20250929 \
  --agent claude --mcp false \
  --output-dir ./eval-sonnet45-original \
  --folder-prefix claude-sonnet-4-5

# 4. Validate downloads
python3 validate_artifacts.py --artifact-dir ./eval-sonnet45-original

# 5. Audit with ground truth (optional but recommended)
python3 audit_artifacts.py \
  --artifact-dir ./eval-sonnet45-original \
  --task-yaml-dir ../../datasets \
  --output-csv sonnet45-audit.csv

# 6. Extract failures for rerun
python3 extract_failing_tasks.py \
  --artifact-dir ./eval-sonnet45-original \
  --rate-limited-only \
  --format launch > rerun-tasks.txt

# 7. Rerun failures (longer delays)
python3 launch_tasks.py \
  --task-file rerun-tasks.txt \
  --model claude-sonnet-4-5-20250929 \
  --agent claude --mcp false \
  --delay 300 \
  --log-file sonnet45-rerun.log

# 8. Download rerun artifacts
python3 download_artifacts.py \
  --start-date 2026-03-02 \
  --model claude-sonnet-4-5-20250929 \
  --agent claude --mcp false \
  --output-dir ./eval-sonnet45-rerun \
  --folder-prefix claude-sonnet-4-5

# 9. Assemble best-of-two
python3 assemble_best_of_n.py \
  --sources "original=./eval-sonnet45-original,rerun=./eval-sonnet45-rerun" \
  --output-dir ./eval-sonnet45-bestof2

# 10. Generate final report
python3 generate_report.py \
  --artifact-dir ./eval-sonnet45-bestof2

# 11. (Optional) Compare with another model
python3 generate_report.py \
  --artifact-dir ./eval-sonnet45-bestof2 \
  --compare-dir ./eval-opus46-bestof2 \
  --compare-label "Claude opus-4-6"
```

## Directory Conventions

### Artifact Folder Naming

```
{model-prefix}-{repo}-{task-hash}
```

Examples:
```
claude-sonnet-4-5-vuls-01441351c3407abfc21c48a38e28828e1b504e0c
codex-gpt52-ansible-12734fa21c08a0ce8c84e533abdc560db2eb1955
claude-opus-4-6-element-web-4c6b0d35abc123
```

### Expected Files Per Artifact

```
{folder}/
├── result.json            # Metrics: resolved, cost, tokens, tool usage
├── agent.log              # JSONL event log from agent execution
├── changes.patch          # Git diff of agent's changes
├── pre_verification.log   # F2P tests before agent (should fail)
├── verification.log       # F2P tests after agent (pass = resolved)
├── p2p_pre_verification.log   # P2P tests before agent (should pass)
└── p2p_verification.log       # P2P tests after agent (should still pass)
```

### Best Practices

- **Use `--log-file`** with `launch_tasks.py` to enable resume on interruption
- **Increase `--delay`** for reruns (300s+) to avoid rate limiting
- **Always validate** before reporting — `validate_artifacts.py` catches corrupt downloads
- **Audit ground truth** for final results — `audit_artifacts.py` catches parser mismatches
- **Use `--exclude-tasks`** to remove known-broken tasks from scoring
- **Save cache files** when downloading large batches — `--cache-file` avoids re-querying the API
