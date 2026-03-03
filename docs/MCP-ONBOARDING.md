# MCP Server Onboarding Guide

This guide walks through integrating an external MCP (Model Context Protocol) server with SWE-bench Pro Runner for A/B testing. It is aimed at teams like Bito who want to evaluate whether their MCP tools improve agent performance on real-world tasks.

> **Resolves [ADR-001](adr/README.md)** — see [#16](https://github.com/thecontextlab/swebench-pro-runner/issues/16).

## Prerequisites

Before starting, you need:

1. A running **MCP server** with an HTTP endpoint (e.g., `https://your-server.example.com/mcp`)
2. A **bearer token** for authentication
3. The server must implement the [Model Context Protocol](https://modelcontextprotocol.io/) specification
4. A fork of this repository with GitHub Actions enabled

## Step 1: Configure the MCP URL

Edit the `config.yaml` for the repository you want to test. Set the `mcp.url` field to your server's endpoint:

```yaml
# datasets/vuls/config.yaml
mcp:
  url: https://your-mcp-server.example.com/mcp
  description: "BitArchitect - indexed vuls codebase"
```

You can configure different URLs per repository, or use the same URL across all repos if your server supports multiple codebases.

## Step 2: Set the Authentication Secret

Add your MCP bearer token as a GitHub repository secret:

1. Go to your fork's **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `MCP_TOKEN`
4. Value: your bearer token

> **Note:** All repositories share a single `MCP_TOKEN` secret. Per-repo token support is tracked in [ADR-003](https://github.com/thecontextlab/swebench-pro-runner/issues/18).

## Step 3: Verify Connectivity

Before spending API credits, validate that the MCP server is reachable.

**Option A: Use the validation workflow**

```bash
gh workflow run validate-infrastructure.yml \
  -f repo=vuls \
  -f task="future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c" \
  -f validation_type=all
```

This runs a zero-cost infrastructure check (no agent invocation).

**Option B: Manual curl test**

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $MCP_TOKEN" \
  https://your-mcp-server.example.com/mcp
```

A `200` response confirms the server is reachable and authenticated.

## Step 4: Run a Treatment Evaluation

Launch a single task with MCP enabled:

```bash
gh workflow run swebench-eval.yml \
  -f repo=vuls \
  -f task="future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c" \
  -f agent=claude \
  -f model="claude-sonnet-4-5-20250929" \
  -f enable_mcp=true
```

The key flag is **`enable_mcp=true`** — this tells the agent wrapper to construct an MCP server configuration and add MCP tools to the allowed tools list.

## Step 5: Compare Baseline vs Treatment

To measure MCP impact, run the same task twice — once without MCP (baseline) and once with MCP (treatment):

**Baseline run:**
```bash
gh workflow run swebench-eval.yml \
  -f repo=vuls \
  -f task="future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c" \
  -f agent=claude \
  -f model="claude-sonnet-4-5-20250929" \
  -f enable_mcp=false
```

**Treatment run:**
```bash
gh workflow run swebench-eval.yml \
  -f repo=vuls \
  -f task="future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c" \
  -f agent=claude \
  -f model="claude-sonnet-4-5-20250929" \
  -f enable_mcp=true
```

Download both `result.json` artifacts and compare:
- `resolved` — did the agent fix the bug?
- `total_cost_usd` — cost difference
- `tool_usage.mcp_tools` — which MCP tools were called and how often
- `duration_seconds` — time difference

## Step 6: Batch Evaluation

For statistically meaningful results, run many tasks with and without MCP:

```bash
# Dry run first — always!
python3 scripts/eval-orchestration/launch_tasks.py \
  --repo vuls --agent claude --model "claude-sonnet-4-5-20250929" \
  --mcp true --dry-run

# If the dry run looks correct, launch for real
python3 scripts/eval-orchestration/launch_tasks.py \
  --repo vuls --agent claude --model "claude-sonnet-4-5-20250929" \
  --mcp true
```

Run the same batch with `--mcp false` to generate baseline data, then use `generate_report.py` to compare results.

## MCP Tool Tracking

When MCP is enabled, the agent's tool calls appear in `result.json` with a namespaced format:

```
mcp__mcp-server__toolName
```

For example, if your MCP server exposes `searchCode`, `searchSymbols`, and `getCode` tools:

```json
{
  "tool_usage": {
    "all_tools": {
      "Bash": 20,
      "Read": 15,
      "Edit": 3,
      "mcp__mcp-server__searchCode": 5,
      "mcp__mcp-server__searchSymbols": 2,
      "mcp__mcp-server__getCode": 1
    },
    "total_tool_calls": 46,
    "mcp_tools": {
      "total_calls": 8,
      "tools": {
        "mcp__mcp-server__searchCode": 5,
        "mcp__mcp-server__searchSymbols": 2,
        "mcp__mcp-server__getCode": 1
      },
      "queries": ["search query 1", "search query 2"]
    }
  }
}
```

> **Note:** The server name `mcp-server` is currently hardcoded. Making it configurable is tracked in [ADR-002](https://github.com/thecontextlab/swebench-pro-runner/issues/17).

## How MCP Works Under the Hood

When `enable_mcp=true`:

1. The workflow reads `mcp.url` from `datasets/{repo}/config.yaml` via `config_loader.py`
2. The URL and token are passed as environment variables (`MCP_URL`, `MCP_TOKEN`) to the Docker container
3. The agent wrapper (`run_claude.py`) constructs an MCP config file:

```json
{
  "mcpServers": {
    "mcp-server": {
      "type": "http",
      "url": "https://your-mcp-server.example.com/mcp",
      "headers": {
        "Authorization": "Bearer <token>"
      }
    }
  }
}
```

4. Claude Code is launched with `--mcp-config /tmp/mcp_config.json` and `--allowedTools` includes `mcp__mcp-server`
5. A runtime `CLAUDE.md` file is written to `/testbed/` with hints about available MCP tools

## Current Limitations

| Limitation | Details | Tracking |
|------------|---------|----------|
| Claude-only | Codex and Gemini wrappers have no MCP code | [ADR-012](https://github.com/thecontextlab/swebench-pro-runner/issues/27) |
| Single shared token | All repos use `secrets.MCP_TOKEN` — no per-repo tokens | [ADR-003](https://github.com/thecontextlab/swebench-pro-runner/issues/18) |
| Hardcoded server name | Always `"mcp-server"` — cannot distinguish providers in analytics | [ADR-002](https://github.com/thecontextlab/swebench-pro-runner/issues/17) |
| Repo-level config only | MCP URL is set per-repo, not per-task or per-task-group | [ADR-009](https://github.com/thecontextlab/swebench-pro-runner/issues/24) |
| No health check | No automated MCP connectivity validation before runs | [ADR-004](https://github.com/thecontextlab/swebench-pro-runner/issues/19) |

## Troubleshooting

### MCP tools not appearing in result.json

- Verify `enable_mcp=true` was passed to the workflow
- Check that `mcp.url` is set in the repo's `config.yaml` (not left empty)
- Confirm `MCP_TOKEN` secret exists in your fork's settings

### Agent not using MCP tools

- The agent decides whether to use MCP tools based on the task. Not all tasks benefit from code search.
- Check `agent.log` for MCP-related messages — look for `mcp__mcp-server` in tool call events
- The runtime `CLAUDE.md` provides hints, but the agent may still prefer built-in tools

### Authentication errors

- Verify the token is valid: `curl -H "Authorization: Bearer $TOKEN" $MCP_URL`
- Check for token expiration — regenerate and update the `MCP_TOKEN` secret if needed
- Ensure the MCP server accepts HTTP bearer token auth (not API key headers or other schemes)

### MCP server timeout

- The agent has a 45-minute timeout (configurable via `agent_timeout_minutes`)
- If MCP calls are slow, the overall run takes longer and may hit the timeout
- Monitor MCP server latency — p99 response times above 10 seconds will degrade agent performance

### Empty MCP URL in config.yaml

Many repos ship with an empty `mcp.url` field:

```yaml
mcp:
  url:   # configure your own
```

You must set this to your server's endpoint. An empty URL with `enable_mcp=true` will result in the agent running without MCP tools (no error, but no MCP either).
