# SWE-bench Pro Evaluation Scripts

Curated, parameterized tools for running SWE-bench Pro evaluations end-to-end: launching tasks, monitoring runs, downloading artifacts, validating results, extracting failures for reruns, assembling best-of-N datasets, and generating reports.

## Prerequisites

- **Python 3.9+** (stdlib only — no pip install needed)
- **`gh` CLI** authenticated (`gh auth status`)
- Access to the `swebench-eval.yml` GitHub Actions workflow

## Scripts

### `_utils.py` — Shared Utilities

Common functions used by all scripts:

| Function | Purpose |
|----------|---------|
| `get_repo_from_folder(folder)` | Extract repo name from folder like `codex-gpt52-{repo}-{hash}` |
| `get_hash_part(folder)` | Extract task hash identifier from folder name |
| `load_result(folder_path)` | Load `result.json` with error handling |
| `extract_metrics(data)` | Normalize metrics across Claude/Codex result.json formats |
| `scan_agent_log(log_path)` | Detect `rate_limit` and `turn.failed` in agent.log |
| `parse_display_title(title)` | Parse GHA displayTitle into repo/task/agent/mcp components |
| `index_artifact_dir(directory)` | Index artifact dir into `{hash_part: path}` mapping |

Known repo list: ansible, element-web, flipt, navidrome, NodeBB, openlibrary, qutebrowser, teleport, tutanota, vuls, webclients

---

### `launch_tasks.py` — Task Launcher

Dispatches evaluation tasks to GitHub Actions with rate-limit-aware delays.

```bash
python3 launch_tasks.py \
  --task-file tasks.txt \
  --model "gpt-5.2-codex" \
  --agent codex \
  --mcp false \
  --delay 120 \
  --log-file launch.log \
  --dry-run
```

**Task file format** (pipe-delimited):
```
ansible|ansible__ansible-12734fa21c08a...
element-web|element-hq__element-web-4c6b0d35...
# Comments and empty lines are skipped
```

| Flag | Description |
|------|-------------|
| `--task-file` | Path to pipe-delimited task file (required) |
| `--model` | Model string, e.g. `gpt-5.2-codex`, `claude-opus-4-6` (required) |
| `--agent` | Agent name: `claude`, `codex`, `gemini` (required) |
| `--mcp` | `true` or `false` (default: false) |
| `--delay` | Seconds between launches (default: 5) |
| `--log-file` | Enables resume — skips tasks already in log |
| `--dry-run` | Print commands without executing |

---

### `monitor_runs.py` — Run Monitor

Polls GitHub Actions for run status with per-repo breakdown.

```bash
# One-shot status
python3 monitor_runs.py --start-date 2026-02-21 --model gpt-5.2-codex

# Watch mode with 60s refresh
python3 monitor_runs.py --start-date 2026-02-21 --model claude-opus-4-6 \
  --watch --interval 60

# Filter by repo
python3 monitor_runs.py --start-date 2026-02-21 --repo flipt --agent codex
```

| Flag | Description |
|------|-------------|
| `--start-date` | Filter runs from this date (YYYY-MM-DD) |
| `--model` | Filter by model string |
| `--agent` | Filter by agent name |
| `--mcp` | Filter by MCP flag |
| `--repo` | Filter by repository |
| `--watch` | Continuously poll until all complete |
| `--interval` | Poll interval in seconds (default: 60) |

---

### `download_artifacts.py` — Artifact Downloader

Downloads evaluation artifacts from completed GitHub Actions runs.

```bash
python3 download_artifacts.py \
  --start-date 2026-02-20 \
  --model "gpt-5.2-codex" \
  --agent codex \
  --mcp false \
  --output-dir ./eval-codex52 \
  --folder-prefix "codex-gpt52" \
  --limit 500
```

| Flag | Description |
|------|-------------|
| `--start-date` / `--end-date` | Date range filter |
| `--model` | Model string filter |
| `--agent` | Agent name filter |
| `--mcp` | MCP flag filter |
| `--output-dir` | Download destination (required) |
| `--folder-prefix` | Prefix for folder names (e.g. `codex-gpt52`) |
| `--cache-file` | Cache GHA run list to avoid repeated API calls |
| `--limit` | Max runs to fetch (default: 500) |

Idempotent — skips already-downloaded artifacts.

---

### `validate_artifacts.py` — Artifact Validator

Checks artifact integrity: file completeness, result.json validity, rate limiting, pre-verification.

```bash
python3 validate_artifacts.py --artifact-dir ./eval-codex52

# Export JSON report
python3 validate_artifacts.py --artifact-dir ./eval-codex52 --output-json report.json
```

Checks performed:
- `result.json` valid JSON with required fields
- `agent.log` exists and is non-trivial (>500 bytes)
- `pre_verification.log` exists (tests should fail before agent runs)
- `verification.log` exists
- Rate limiting / turn.failed detection in agent.log
- Consistency: `result.json` resolved matches verification.log outcome

---

### `extract_failing_tasks.py` — Failing Task Extractor

Identifies tasks that failed for reruns.

```bash
# Launch-ready format (pipe directly to launch_tasks.py)
python3 extract_failing_tasks.py --artifact-dir ./eval-codex52 --format launch > rerun.txt

# Only rate-limited failures
python3 extract_failing_tasks.py --artifact-dir ./eval-codex52 \
  --rate-limited-only --format launch

# CSV with metrics
python3 extract_failing_tasks.py --artifact-dir ./eval-codex52 --format csv

# Exclude known broken tasks
python3 extract_failing_tasks.py --artifact-dir ./eval-codex52 \
  --exclude-broken f8e7fea0becae25ae20606f1422068137189fe9e
```

| Flag | Description |
|------|-------------|
| `--artifact-dir` | Directory to scan (required) |
| `--format` | `launch` (pipe-delimited) or `csv` |
| `--rate-limited-only` | Only include rate-limited failures |
| `--exclude-broken` | Hash parts of broken tasks to skip |
| `--output` | Output file (default: stdout) |

---

### `assemble_best_of_n.py` — Best-of-N Dataset Assembly

Selects the best result per task across multiple runs.

```bash
# Best-of-two
python3 assemble_best_of_n.py \
  --sources "original=/path/to/run1,rerun=/path/to/run2" \
  --output-dir ./eval-bestof2

# Best-of-three, excluding broken tasks
python3 assemble_best_of_n.py \
  --sources "original=/path1,rerun=/path2,tier5=/path3" \
  --output-dir ./eval-bestof3 \
  --exclude-tasks f8e7fea0becae25ae20606f1422068137189fe9e
```

**Selection rules** (per task, across all available runs):
1. `resolved=true` wins over `resolved=false`
2. If tied, prefer no rate limiting
3. If tied, prefer no `turn.failed`
4. If tied, prefer latest source (sources listed later have higher priority)

Outputs:
- Copies best artifacts to output directory
- `selection_metadata.csv` — which source was picked per task and why

---

### `generate_report.py` — Report Generator

Generates markdown report and CSV from evaluation artifacts.

```bash
# Markdown + CSV
python3 generate_report.py --artifact-dir ./eval-codex52-bestof3

# With baseline comparison
python3 generate_report.py --artifact-dir ./eval-codex52-bestof3 \
  --compare-dir ./eval-opus46-baseline \
  --compare-label "Claude opus-4-6"

# Exclude broken tasks
python3 generate_report.py --artifact-dir ./eval-codex52 \
  --exclude-tasks f8e7fea0becae25ae20606f1422068137189fe9e
```

| Flag | Description |
|------|-------------|
| `--artifact-dir` | Directory with artifacts (required) |
| `--output-format` | `md`, `csv`, or `md,csv` (default: both) |
| `--output-dir` | Where to write reports (default: artifact-dir) |
| `--exclude-tasks` | Broken task hash parts to exclude from scoring |
| `--compare-dir` | Baseline artifacts for head-to-head comparison |
| `--compare-label` | Label for baseline in comparison tables |

---

## End-to-End Workflow

```
Launch → Monitor → Download → Validate → Extract failures → Rerun → Assemble → Report
```

### Example: Codex gpt-5.2 Baseline Evaluation

```bash
# 1. Launch 100 tasks
python3 launch_tasks.py \
  --task-file ../datasets/100-task-list.txt \
  --model gpt-5.2-codex --agent codex --mcp false \
  --delay 120 --log-file codex52-launch.log

# 2. Monitor progress
python3 monitor_runs.py \
  --start-date 2026-02-20 --model gpt-5.2-codex --watch --interval 120

# 3. Download completed artifacts
python3 download_artifacts.py \
  --start-date 2026-02-20 --model gpt-5.2-codex --agent codex --mcp false \
  --output-dir ./eval-codex52-original --folder-prefix codex-gpt52

# 4. Validate downloads
python3 validate_artifacts.py --artifact-dir ./eval-codex52-original

# 5. Extract failing tasks for rerun
python3 extract_failing_tasks.py \
  --artifact-dir ./eval-codex52-original \
  --rate-limited-only --format launch > rerun-tasks.txt

# 6. Rerun failing tasks (with longer delays to avoid rate limits)
python3 launch_tasks.py \
  --task-file rerun-tasks.txt \
  --model gpt-5.2-codex --agent codex --mcp false \
  --delay 300 --log-file codex52-rerun.log

# 7. Download rerun artifacts
python3 download_artifacts.py \
  --start-date 2026-02-21 --model gpt-5.2-codex --agent codex --mcp false \
  --output-dir ./eval-codex52-rerun --folder-prefix codex-gpt52

# 8. Assemble best-of-two
python3 assemble_best_of_n.py \
  --sources "original=./eval-codex52-original,rerun=./eval-codex52-rerun" \
  --output-dir ./eval-codex52-bestof2

# 9. Generate final report
python3 generate_report.py \
  --artifact-dir ./eval-codex52-bestof2 \
  --exclude-tasks f8e7fea0becae25ae20606f1422068137189fe9e
```

### Example: Claude opus-4-6 with Comparison

```bash
# Launch and collect as above, then generate comparison report
python3 generate_report.py \
  --artifact-dir ./eval-opus46-baseline \
  --compare-dir ./eval-codex52-bestof3 \
  --compare-label "Codex gpt-5.2"
```

## Directory Conventions

### Artifact Folder Naming
```
{model-prefix}-{repo}-{task-hash}
```
Examples:
- `codex-gpt52-vuls-01441351c3407abfc21c48a38e28828e1b504e0c`
- `claude-opus-4-6-element-web-4c6b0d35...`

### Expected Files Per Artifact
```
{folder}/
├── result.json            # Metrics: resolved, cost, tokens, tool usage
├── agent.log              # JSONL event log from agent execution
├── changes.patch          # Git diff of agent's changes
├── pre_verification.log   # Tests before agent (should fail)
└── verification.log       # Tests after agent (pass = resolved)
```

### result.json Format
```json
{
  "resolved": true,
  "task_id": "org__repo-hash",
  "duration_seconds": 180,
  "duration_api_seconds": 45,
  "total_cost_usd": 1.23,
  "tokens": {"input": 50000, "output": 5000, "cache_read": 20000},
  "tool_usage": {"total_tool_calls": 42, "all_tools": {"Bash": 20, "Read": 15}},
  "num_turns": 25,
  "model": "gpt-5.2-codex"
}
```
