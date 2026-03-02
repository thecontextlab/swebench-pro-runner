# Analytics

This document covers the `result.json` schema, metrics extraction pipeline, verification log parsing, cost calculation, and audit tools.

## result.json Schema

Every evaluation produces a `result.json` with the following structure:

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `task` | string | Task identifier (e.g., `future-architect__vuls-abc123`) |
| `status` | string | `"success"` or `"failed"` |
| `resolved` | boolean | Whether the task was resolved (F2P pass AND no P2P regression) |
| `f2p_resolved` | boolean | Whether all fail-to-pass tests passed |
| `p2p_no_regression` | boolean | Whether all pass-to-pass tests still pass |
| `model` | string | Model used (e.g., `claude-sonnet-4-5-20250929`) |
| `mcp_enabled` | boolean | Whether MCP server was enabled |
| `agent_exit_code` | integer | Exit code from the agent process |
| `verification_exit_code` | integer | Exit code from F2P test execution |
| `exit_code_resolved` | boolean | Whether resolution was determined by exit code (fallback) |
| `timestamp` | string | ISO 8601 timestamp |
| `session_id` | string | Agent session identifier |
| `claude_code_version` | string | Claude Code CLI version (null for other agents) |

### Test Results

```json
{
  "tests": {
    "total": 2,
    "passed": 2,
    "failed": 0
  },
  "fail_to_pass_results": {
    "TestConvert": "PASS",
    "TestConvert/FortiSwitch-108E": "PASS"
  },
  "p2p_tests": {
    "total": 17,
    "passed": 17,
    "failed": 0
  },
  "pass_to_pass_results": {
    "TestConvert/Cisco_NX-OS_Version_7.1(4)N1(1)": "PASS",
    "TestConvert/FortiGate-50E": "PASS"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `tests.total` | integer | Total number of F2P tests |
| `tests.passed` | integer | F2P tests that passed |
| `tests.failed` | integer | F2P tests that failed |
| `fail_to_pass_results` | object | Per-test outcome: `"PASS"` or `"FAIL"` |
| `p2p_tests.total` | integer | Total P2P tests |
| `p2p_tests.passed` | integer | P2P tests that passed |
| `p2p_tests.failed` | integer | P2P tests that failed (regressions) |
| `pass_to_pass_results` | object | Per-P2P-test outcome |

### Agent Metrics

```json
{
  "duration_seconds": 85.8,
  "duration_api_seconds": 42.1,
  "total_cost_usd": 0.33,
  "num_turns": 12,
  "tokens": {
    "input": 48000,
    "output": 3801,
    "cache_read": 256474,
    "cache_creation": 12000
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `duration_seconds` | float | Total wall-clock time |
| `duration_api_seconds` | float | Time spent on API calls |
| `total_cost_usd` | float | Estimated API cost in USD |
| `num_turns` | integer | Number of agent turns (API round-trips) |
| `tokens.input` | integer | Total input tokens |
| `tokens.output` | integer | Total output tokens |
| `tokens.cache_read` | integer | Tokens read from cache |
| `tokens.cache_creation` | integer | Tokens written to cache |

### Code Changes

```json
{
  "code_changes": {
    "lines_added": 45,
    "lines_removed": 12,
    "lines_changed": 57,
    "files_modified": 3,
    "files": [
      "contrib/snmp2cpe/pkg/cpe/cpe.go",
      "contrib/snmp2cpe/pkg/cpe/cpe_test.go"
    ]
  }
}
```

### Model Usage Breakdown

```json
{
  "model_usage": {
    "claude-sonnet-4-5-20250929": {
      "inputTokens": 48000,
      "outputTokens": 3801,
      "cacheReadInputTokens": 256474,
      "cacheCreationInputTokens": 12000,
      "costUSD": 0.33,
      "contextWindow": 200000
    }
  }
}
```

When multiple models are used in a single run, each gets its own entry.

### Tool Usage

```json
{
  "tool_usage": {
    "all_tools": {
      "Read": 15,
      "Edit": 3,
      "Bash": 20,
      "Grep": 5,
      "Glob": 2,
      "mcp__code-search__searchCode": 3
    },
    "total_tool_calls": 48,
    "mcp_tools": {
      "total_calls": 3,
      "tools": {
        "mcp__code-search__searchCode": 3
      },
      "queries": [
        {
          "tool": "mcp__code-search__searchCode",
          "id": "tool_abc123",
          "input": {"query": "FortiSwitch CPE conversion"},
          "tokens": {"input": 1200, "output": 500}
        }
      ]
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `tool_usage.all_tools` | object | Tool name → call count (all tools) |
| `tool_usage.total_tool_calls` | integer | Sum of all tool calls |
| `tool_usage.mcp_tools.total_calls` | integer | Total MCP tool calls |
| `tool_usage.mcp_tools.tools` | object | MCP tool name → call count |
| `tool_usage.mcp_tools.queries` | array | Detailed MCP query log |

## Metrics Extraction Pipeline

`extract_metrics.py` reads three artifact files and produces `result.json`:

```
agent.log ──────────┐
                    ├──▶ extract_metrics.py ──▶ result.json
verification.log ──┤
                    │
changes.patch ──────┘
```

### Source 1: Agent Log (`agent.log`)

The agent log is the primary source for token usage, cost, duration, and tool calls.

#### Claude JSONL Format

Claude Code outputs JSONL with these event types:

```jsonl
{"type":"system","subtype":"init","session_id":"...","claude_code_version":"1.0.0"}
{"type":"assistant","message":{"id":"msg_123","model":"claude-sonnet-4-5","content":[{"type":"tool_use","name":"Read","id":"toolu_123","input":{"file_path":"/testbed/main.go"}}],"usage":{"input_tokens":1200,"output_tokens":50,"cache_read_input_tokens":500}}}
{"type":"result","duration_ms":85800,"duration_api_ms":42100,"total_cost_usd":0.33,"num_turns":12,"usage":{"input_tokens":48000,"output_tokens":3801,"cache_read_input_tokens":256474}}
```

The parser:
1. Extracts session info from `system/init` events
2. Tracks tool calls from `assistant` messages' `content[].type=="tool_use"`
3. Accumulates per-message token usage (deduplicating by message ID)
4. Uses the `result` event for aggregate metrics (preferred over accumulation)
5. Falls back to accumulated message metrics if no `result` event exists

#### Codex JSONL Format

Codex CLI outputs JSONL with these event types:

```jsonl
{"type":"thread.started","thread_id":"thread_abc123"}
{"type":"turn.started"}
{"type":"item.completed","item":{"type":"command_execution","command":"ls /testbed"}}
{"type":"item.completed","item":{"type":"file_change","path":"main.go"}}
{"type":"item.completed","item":{"type":"mcp_tool_call","tool":"searchCode","server":"code-search"}}
{"type":"turn.completed","usage":{"input_tokens":5000,"output_tokens":800,"cached_input_tokens":2000}}
{"type":"error","message":"Rate limit reached for ... TPM. Used 150000"}
```

The parser maps Codex event types to normalized tool names:
- `command_execution` → `Bash`
- `file_change` → `FileEdit`
- `mcp_tool_call` → `mcp__{server}__{tool}`
- `reasoning` → `Reasoning`

#### Gemini Stream-JSON Format

Gemini CLI outputs stream-json with these event types:

```jsonl
{"type":"init","session_id":"...","model":"models/gemini-3-pro-preview"}
{"type":"tool_result","tool_id":"readFile-12345-abc"}
{"type":"result","stats":{"input_tokens":5000,"output_tokens":800,"duration_ms":45000,"tool_calls":15}}
```

The parser extracts the model name from `init`, counts tools from `tool_result`, and reads aggregate stats from `result`.

### Source 2: Verification Log (`verification.log`)

The verification log is parsed by framework-specific parsers to determine per-test outcomes.

#### Resolution Logic

```python
# 1. Parse verification.log with framework-specific parser
outcomes = parser(fail_to_pass, verification_log_text)

# 2. Determine F2P resolution
f2p_resolved = (tests_failed == 0 and tests_passed > 0)

# 3. Determine P2P regression
p2p_no_regression = (p2p_tests_failed == 0)

# 4. Final resolution = both must be true
resolved = f2p_resolved and p2p_no_regression
```

#### Framework Parsers

**pytest** (`_parse_pytest`):
```
test/path/file.py::TestClass::test_method PASSED
test/path/file.py::TestClass::test_method FAILED
```
Handles inline and multi-line formats where PASSED/FAILED appears on a subsequent line. Also handles XFAIL (expected failure) and XPASS (unexpected pass) as passing states.

**Go test** (`_parse_go`):
```
--- PASS: TestConvert (0.00s)
--- FAIL: TestConvert/FortiSwitch-108E (0.05s)
```
Matches the `--- PASS/FAIL: TestName` pattern with regex.

**Go custom / Teleport** (`_parse_go_custom`):
```
EXPECTED: Test function TestName does not exist yet
--- PASS: TestName (0.00s)
```
Handles Teleport's custom runner that reports non-existent tests differently.

**Jest** (`_parse_jest`):
```
PASS test/components/App.test.tsx
FAIL test/components/Broken.test.tsx
  ✓ should render (5ms)
  ✕ should handle error (12ms)
```
Parses file-level PASS/FAIL and individual test checkmarks. Test names use `file | suite | description` format.

**Jest workspace** (`_parse_jest_workspace`):
```
Running test: test/path/file.spec.ts
...test output...
Test execution completed for test/path/file.spec.ts
```
Uses section delimiters rather than individual test parsing.

**Mocha** (`_parse_mocha`):
```json
{"stats":{"passes":5,"failures":1},"tests":[{"title":"should create","fullTitle":"Topics should create","err":{}}]}
```
Parses JSON reporter output. Tests with empty `err` objects passed; non-empty `err` objects failed.

**Custom / Tutanota** (`_parse_custom_tutanota`):
```
All 42 assertions passed
```
or:
```
3 out of 42 assertions failed
```

### Source 3: Changes Patch (`changes.patch`)

The patch file is a standard `git diff` output. The parser counts:
- Files modified (lines matching `^diff --git a/`)
- Lines added (lines starting with `+` but not `+++`)
- Lines removed (lines starting with `-` but not `---`)

## Cost Calculation

### Claude Models

| Model | Input (/1M) | Output (/1M) | Cache Read (/1M) | Cache Create (/1M) |
|-------|------------|-------------|-----------------|-------------------|
| claude-sonnet-4-5 | $3.00 | $15.00 | $0.30 | $3.75 |
| claude-opus-4-5 | $15.00 | $75.00 | $1.50 | $18.75 |
| claude-haiku-4-5 | $0.80 | $4.00 | $0.08 | $1.00 |

**Formula:**
```
cost = (input_tokens / 1M) × input_price
     + (output_tokens / 1M) × output_price
     + (cache_read_tokens / 1M) × cache_read_price
     + (cache_creation_tokens / 1M) × cache_creation_price
```

Claude includes cost in the `result` event, so the formula is only used as a fallback when accumulating from individual messages.

### OpenAI / Codex Models

| Model | Input (/1M) | Output (/1M) | Cached Input (/1M) |
|-------|------------|-------------|-------------------|
| gpt-5.3-codex | $1.25 | $10.00 | $0.125 |
| gpt-5.2-codex | $1.75 | $14.00 | $0.175 |
| gpt-4o | $2.50 | $10.00 | $1.25 |
| gpt-4o-mini | $0.15 | $0.60 | $0.075 |

**Formula:**
```
non_cached_input = max(0, input_tokens - cached_input_tokens)
cost = (non_cached_input / 1M) × input_price
     + (output_tokens / 1M) × output_price
     + (cached_input_tokens / 1M) × cached_price
```

### Gemini Models

| Model | Input (/1M) | Output (/1M) |
|-------|------------|-------------|
| gemini-3-pro-preview | $1.25 | $5.00 |
| gemini-2.0-flash | $0.075 | $0.30 |

## Audit Tools

### `audit_artifacts.py` — Ground-Truth Verification

The audit tool provides the authoritative determination of whether a task was resolved. It cross-references three sources:

1. **Task YAML** → `fail_to_pass` list (what tests must pass)
2. **verification.log** → actual test output (what happened)
3. **result.json** → claimed `resolved` status (what was reported)

**Classification per test:**

| Category | Meaning |
|----------|---------|
| TP (True Positive) | Test passed AND was expected to pass → correct |
| FP (False Positive) | result.json says resolved but test actually failed |
| FN (False Negative) | result.json says unresolved but test actually passed |
| TN (True Negative) | Test failed AND was expected to fail → correct |

**Output CSV columns:**
```
task_id, repo, framework, f2p_count, f2p_passed, f2p_failed, audit_resolved,
claimed_resolved, match, discrepancy_type, details
```

### `validate_artifacts.py` — Integrity Checks

Validates that downloaded artifacts are complete and consistent:

| Check | What It Catches |
|-------|-----------------|
| `result.json` exists | Failed downloads, container crashes |
| `result.json` valid JSON | Truncated writes, encoding errors |
| Required fields present | Schema version mismatches |
| `agent.log` > 500 bytes | Agent never started, early crash |
| `pre_verification.log` exists | Missing pre-verification step |
| `verification.log` exists | Missing post-verification step |
| No rate limiting | API rate limit exhaustion |
| No `turn.failed` | Agent turn failures |
| Consistency | `resolved` matches exit code |

## Reporting

### `generate_report.py` Output

**Markdown report sections:**
1. **Summary**: Total tasks, resolved count, pass rate, aggregate cost, mean duration
2. **Per-Repository Breakdown**: Resolution rate, cost, duration by repo
3. **Cost Analysis**: Total, mean, median, p95, min, max
4. **Token Usage**: Input, output, cache read, cache creation totals and means
5. **Tool Usage**: Most-used tools, MCP tool breakdown
6. **Comparison** (optional): Head-to-head with baseline on all metrics

**CSV columns:**
```
task_id, repo, resolved, duration_seconds, duration_api_seconds, total_cost_usd,
tokens_input, tokens_output, tokens_cache_read, total_tool_calls, num_turns, model
```

### Comparison Mode

When `--compare-dir` is provided, the report includes:
- Side-by-side resolution rates per repository
- Win/loss/tie analysis (which model resolved more tasks)
- Cost and duration comparison
- Tasks resolved by one model but not the other

## MCP Tool Usage Analysis

For A/B testing analysis, key metrics to compare:

### Resolution Rate Impact
```
baseline_pass_rate = resolved_baseline / total_tasks
treatment_pass_rate = resolved_mcp / total_tasks
lift = (treatment_pass_rate - baseline_pass_rate) / baseline_pass_rate
```

### Tool Call Patterns
- Average MCP tool calls per task (treatment group)
- Correlation between MCP tool usage and resolution
- Most frequently used MCP tools
- Token overhead from MCP (additional tokens consumed)

### Cost Impact
- Mean cost difference (treatment - baseline)
- Cost per resolved task (both groups)
- MCP token overhead as percentage of total

These analyses can be extracted from `result.json` fields across a set of artifacts using the orchestration scripts and standard data analysis tools.
