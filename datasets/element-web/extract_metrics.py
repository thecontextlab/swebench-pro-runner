#!/usr/bin/env python3
"""
Extract SWE-bench evaluation metrics from agent trajectory and test results.

Parses:
- agent.log (JSONL trajectory) for token usage, cost, duration
- verification.log for test results
- changes.patch for code change metrics

Outputs enhanced result.json matching SWE-bench standard format.
"""
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Framework classification by repository (mirrors _utils.py / audit_artifacts.py)
# ---------------------------------------------------------------------------
PYTEST_REPOS = {"ansible", "openlibrary", "qutebrowser"}
GO_REPOS = {"vuls", "flipt", "navidrome"}
GO_CUSTOM_REPOS = {"teleport"}
JEST_REPOS = {"element-web"}
JEST_WORKSPACE_REPOS = {"webclients"}
MOCHA_REPOS = {"NodeBB"}
CUSTOM_REPOS = {"tutanota"}


def _get_framework_for_repo(repo):
    """Return the test framework name for a given repo."""
    if repo in PYTEST_REPOS:
        return "pytest"
    if repo in GO_REPOS:
        return "go"
    if repo in GO_CUSTOM_REPOS:
        return "go_custom"
    if repo in JEST_REPOS:
        return "jest"
    if repo in JEST_WORKSPACE_REPOS:
        return "jest_workspace"
    if repo in MOCHA_REPOS:
        return "mocha"
    if repo in CUSTOM_REPOS:
        return "custom"
    return "unknown"


def _strip_ansi(text):
    """Remove ANSI escape codes from text."""
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def parse_codex_jsonl(content: str) -> dict:
    """Parse Codex CLI's JSONL output format.

    Codex JSONL event types:
      thread.started  — session start, has thread_id
      turn.started    — new turn begins
      item.started    — item begins (status in_progress)
      item.completed  — item completes: command_execution, file_change,
                        mcp_tool_call, reasoning, todo_list, agent_message
      item.updated    — item updated (e.g. todo_list checkmarks)
      turn.completed  — turn ends, has usage {input_tokens, cached_input_tokens, output_tokens}
      error           — error event (rate limits, etc.)
    """
    metrics = {
        "duration_seconds": 0,
        "duration_api_seconds": 0,
        "total_cost_usd": 0,
        "num_turns": 0,
        "tokens": {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_creation": 0,
        },
        "model_usage": {},
        "session_id": None,
        "claude_code_version": None,
        "mcp_tools": {
            "total_calls": 0,
            "tools": {},
            "queries": [],
        },
        "all_tools": {},
    }

    errors = []
    # Detect model from wrapper output (e.g. "[wrapper] Model: gpt-5.2-codex")
    detected_model = "gpt-5.2-codex"  # default
    model_match = re.search(r'\[wrapper\] Model:\s*(\S+)', content)
    if model_match:
        detected_model = model_match.group(1)

    for line in content.split('\n'):
        line = line.strip()
        if not line or not line.startswith('{'):
            continue
        try:
            event = json.loads(line)
            event_type = event.get("type")

            # Extract thread ID from thread.started
            if event_type == "thread.started":
                metrics["session_id"] = event.get("thread_id")

            # Count tool usage from item.completed events
            elif event_type == "item.completed":
                item = event.get("item", {})
                item_type = item.get("type", "")

                if item_type == "command_execution":
                    # All codex commands are shell commands (equivalent to Bash)
                    metrics["all_tools"]["Bash"] = metrics["all_tools"].get("Bash", 0) + 1

                elif item_type == "file_change":
                    # File edits (equivalent to Claude's Edit/Write)
                    metrics["all_tools"]["FileEdit"] = metrics["all_tools"].get("FileEdit", 0) + 1

                elif item_type == "mcp_tool_call":
                    tool_name = item.get("tool", "unknown")
                    full_name = f"mcp__{item.get('server', 'unknown')}__{tool_name}"
                    metrics["all_tools"][full_name] = metrics["all_tools"].get(full_name, 0) + 1
                    metrics["mcp_tools"]["total_calls"] += 1
                    metrics["mcp_tools"]["tools"][full_name] = metrics["mcp_tools"]["tools"].get(full_name, 0) + 1
                    metrics["mcp_tools"]["queries"].append({
                        "tool": full_name,
                        "id": item.get("id", ""),
                        "input": item.get("arguments", {}),
                    })

                elif item_type == "reasoning":
                    metrics["all_tools"]["Reasoning"] = metrics["all_tools"].get("Reasoning", 0) + 1

                elif item_type == "todo_list":
                    metrics["all_tools"]["TodoList"] = metrics["all_tools"].get("TodoList", 0) + 1

                elif item_type == "agent_message":
                    metrics["all_tools"]["AgentMessage"] = metrics["all_tools"].get("AgentMessage", 0) + 1

            # Track errors and rate limits
            elif event_type == "error":
                error_msg = event.get("message", "")
                errors.append(error_msg)
                if "Rate limit reached" in error_msg and "TPM" in error_msg:
                    match = re.search(r"Used (\d+)", error_msg)
                    if match:
                        used_tokens = int(match.group(1))
                        metrics["tokens"]["input"] = max(metrics["tokens"]["input"], used_tokens)

            # Extract turn info
            elif event_type == "turn.started":
                metrics["num_turns"] += 1

            # Accumulate usage from turn.completed events (may have multiple turns)
            elif event_type == "turn.completed":
                usage = event.get("usage", {})
                if usage:
                    metrics["tokens"]["input"] += usage.get("input_tokens", 0)
                    metrics["tokens"]["output"] += usage.get("output_tokens", 0)
                    metrics["tokens"]["cache_read"] += usage.get("cached_input_tokens", 0)

        except json.JSONDecodeError:
            continue

    # Build model_usage breakdown
    if metrics["tokens"]["input"] > 0 or metrics["tokens"]["output"] > 0:
        # Pricing per 1M tokens:
        # gpt-5.2-codex: $1.75 input, $14.00 output, $0.175 cached input
        # gpt-5.3-codex: $1.25 input, $10.00 output, $0.125 cached input
        # gpt-4o: $2.50 input, $10.00 output, $1.25 cached input
        if "5.2" in detected_model:
            price_input, price_output, price_cached = 1.75, 14.00, 0.175
        elif "5.3" in detected_model:
            price_input, price_output, price_cached = 1.25, 10.00, 0.125
        elif "4o-mini" in detected_model:
            price_input, price_output, price_cached = 0.15, 0.60, 0.075
        elif "4o" in detected_model:
            price_input, price_output, price_cached = 2.50, 10.00, 1.25
        else:
            # Default to gpt-5.2-codex pricing
            price_input, price_output, price_cached = 1.75, 14.00, 0.175

        # Non-cached input = total input - cached input
        non_cached_input = max(0, metrics["tokens"]["input"] - metrics["tokens"]["cache_read"])
        cost = (
            (non_cached_input / 1_000_000) * price_input
            + (metrics["tokens"]["output"] / 1_000_000) * price_output
            + (metrics["tokens"]["cache_read"] / 1_000_000) * price_cached
        )
        metrics["total_cost_usd"] = round(cost, 6)

        metrics["model_usage"] = {
            detected_model: {
                "inputTokens": metrics["tokens"]["input"],
                "outputTokens": metrics["tokens"]["output"],
                "cacheReadInputTokens": metrics["tokens"]["cache_read"],
                "cacheCreationInputTokens": 0,
                "costUSD": metrics["total_cost_usd"],
                "contextWindow": 400000,
            }
        }

    return metrics


def parse_cursor_json(content: str) -> dict:
    """Parse Cursor Agent CLI's JSON output format.

    Cursor CLI (beta) -- format may evolve. This parser is defensive
    and falls back to extracting what it can from wrapper markers.
    Cursor uses subscription-based pricing, so cost is $0.00 (ADR-015).
    """
    metrics = {
        "duration_seconds": 0,
        "duration_api_seconds": 0,
        "total_cost_usd": 0,
        "cost_model": "subscription",
        "num_turns": 0,
        "tokens": {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_creation": 0,
        },
        "model_usage": {},
        "session_id": None,
        "claude_code_version": None,
        "mcp_tools": {
            "total_calls": 0,
            "tools": {},
            "queries": [],
        },
        "all_tools": {},
    }

    # Detect model from wrapper output
    model_match = re.search(r'\[wrapper\] Model:\s*(\S+)', content)
    detected_model = model_match.group(1) if model_match else "cursor-default"

    # Extract duration from wrapper output
    duration_match = re.search(r'\[wrapper\] Total duration:\s*([\d.]+)s', content)
    if duration_match:
        metrics["duration_seconds"] = float(duration_match.group(1))

    # Detect idle timeout (ADR-016)
    if "[wrapper] Cursor idle for" in content:
        metrics["idle_timeout_triggered"] = True

    # Parse JSON lines defensively -- extract what we can
    for line in content.split('\n'):
        line = line.strip()
        if not line or not line.startswith('{'):
            continue
        try:
            event = json.loads(line)
            event_type = event.get("type", "")

            # Count turns from any turn-like events
            if "turn" in event_type and "started" in event_type:
                metrics["num_turns"] += 1

            # Extract token usage if present
            usage = event.get("usage", {})
            if usage:
                metrics["tokens"]["input"] += usage.get("input_tokens", 0)
                metrics["tokens"]["output"] += usage.get("output_tokens", 0)
                metrics["tokens"]["cache_read"] += usage.get("cached_input_tokens", usage.get("cache_read_input_tokens", 0))

            # Extract tool usage from tool-related events
            tool_name = event.get("tool", event.get("name", ""))
            if tool_name and ("tool" in event_type or "item" in event_type):
                metrics["all_tools"][tool_name] = metrics["all_tools"].get(tool_name, 0) + 1

            # Extract session/result info
            if event_type == "result" or event_type == "summary":
                metrics["duration_seconds"] = event.get("duration_ms", event.get("duration_seconds", 0))
                if isinstance(metrics["duration_seconds"], (int, float)) and metrics["duration_seconds"] > 1000:
                    metrics["duration_seconds"] = metrics["duration_seconds"] / 1000  # ms to seconds

        except json.JSONDecodeError:
            continue

    # Build model usage if we have token data
    if metrics["tokens"]["input"] > 0 or metrics["tokens"]["output"] > 0:
        metrics["model_usage"] = {
            detected_model: {
                "inputTokens": metrics["tokens"]["input"],
                "outputTokens": metrics["tokens"]["output"],
                "cacheReadInputTokens": metrics["tokens"]["cache_read"],
                "cacheCreationInputTokens": 0,
                "costUSD": 0,  # Subscription model
                "contextWindow": 200000,
            }
        }

    return metrics


def parse_gemini_json(gemini_data: dict) -> dict:
    """Parse Gemini CLI's JSON output format."""
    metrics = {
        "duration_seconds": 0,
        "duration_api_seconds": 0,
        "total_cost_usd": 0,
        "num_turns": 0,
        "tokens": {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_creation": 0,
        },
        "model_usage": {},
        "session_id": gemini_data.get("session_id"),
        "claude_code_version": None,
        "mcp_tools": {
            "total_calls": 0,
            "tools": {},
            "queries": [],
        },
        "all_tools": {},
    }

    stats = gemini_data.get("stats", {})

    # Extract model usage and token counts
    models = stats.get("models", {})
    for model_name, model_stats in models.items():
        api = model_stats.get("api", {})
        tokens = model_stats.get("tokens", {})

        # Calculate duration from latency (Gemini reports in ms)
        metrics["duration_api_seconds"] = api.get("totalLatencyMs", 0) / 1000

        # Extract token counts
        metrics["tokens"]["input"] = tokens.get("input", 0) + tokens.get("prompt", 0)
        metrics["tokens"]["output"] = tokens.get("candidates", 0)
        metrics["tokens"]["cache_read"] = tokens.get("cached", 0)

        # Total tokens for model usage
        total_tokens = tokens.get("total", 0)
        metrics["model_usage"][model_name] = {
            "input_tokens": metrics["tokens"]["input"],
            "output_tokens": metrics["tokens"]["output"],
            "total_tokens": total_tokens
        }

        metrics["num_turns"] = api.get("totalRequests", 0)

        # Calculate cost (rough estimate for Gemini models)
        # Gemini 2.5 Pro: $1.25 per 1M input tokens, $5.00 per 1M output tokens
        # Gemini 2.5 Flash: $0.075 per 1M input tokens, $0.30 per 1M output tokens
        if "pro" in model_name.lower():
            input_cost = (metrics["tokens"]["input"] / 1_000_000) * 1.25
            output_cost = (metrics["tokens"]["output"] / 1_000_000) * 5.00
        else:  # flash or other models
            input_cost = (metrics["tokens"]["input"] / 1_000_000) * 0.075
            output_cost = (metrics["tokens"]["output"] / 1_000_000) * 0.30

        metrics["total_cost_usd"] = round(input_cost + output_cost, 6)

    # Extract tool usage
    tools = stats.get("tools", {})
    if tools:
        by_name = tools.get("byName", {})
        for tool_name, tool_stats in by_name.items():
            count = tool_stats.get("count", 0)
            metrics["all_tools"][tool_name] = count

            # Track MCP tools
            if tool_name.startswith("mcp__"):
                metrics["mcp_tools"]["total_calls"] += count
                metrics["mcp_tools"]["tools"][tool_name] = count

        # Calculate total duration from tool durations
        metrics["duration_seconds"] = tools.get("totalDurationMs", 0) / 1000

    # Extract file changes if available
    files = stats.get("files", {})
    if files:
        metrics["lines_added"] = files.get("totalLinesAdded", 0)
        metrics["lines_removed"] = files.get("totalLinesRemoved", 0)

    return metrics


def parse_trajectory(agent_log_path: str) -> dict:
    """Extract metrics from JSONL trajectory file (Claude) or JSON output (Gemini)."""
    metrics = {
        "duration_seconds": 0,
        "duration_api_seconds": 0,
        "total_cost_usd": 0,
        "num_turns": 0,
        "tokens": {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_creation": 0,
        },
        "model_usage": {},
        "session_id": None,
        "claude_code_version": None,
        # MCP tool usage tracking
        "mcp_tools": {
            "total_calls": 0,
            "tools": {},  # tool_name -> count
            "queries": [],  # list of {tool, query} for analysis
        },
        "all_tools": {},  # all tool usage counts
    }

    if not os.path.exists(agent_log_path):
        return metrics

    with open(agent_log_path, "r") as f:
        content = f.read()

    # First, check if this is Gemini's stream-json format (JSONL with events)
    # or the final summary JSON
    is_gemini_stream = False
    gemini_summary = None

    # Detect Claude JSONL format (has "system" and "assistant" type entries)
    is_claude_jsonl = '{"type":"system"' in content or '{"type":"assistant"' in content

    # Check for Gemini stream-json format (only if NOT Claude JSONL)
    if not is_claude_jsonl and ('{"type":"init"' in content or '{"type":"message"' in content or '{"type":"result"' in content):
        is_gemini_stream = True
        tool_counts = {}
        total_tool_calls = 0
        model_name = "gemini-2.5-pro"  # Default

        # Parse stream-json format and extract metrics
        for line in content.split('\n'):
            line = line.strip()
            if line and line.startswith('{'):
                try:
                    event = json.loads(line)
                    event_type = event.get("type")

                    # Extract session ID and model from init event
                    if event_type == "init":
                        gemini_summary = {"session_id": event.get("session_id")}
                        # Extract model name from init event (e.g., "models/gemini-2.5-pro")
                        model = event.get("model", "")
                        if model:
                            # Remove "models/" prefix if present
                            model_name = model.replace("models/", "")

                    # Count tool calls from tool_result events
                    elif event_type == "tool_result":
                        tool_id = event.get("tool_id", "")
                        # Extract tool name from tool_id (format: toolname-timestamp-hash)
                        tool_name = tool_id.split('-')[0] if tool_id else "unknown"
                        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                        total_tool_calls += 1

                    # Extract final stats from result event
                    elif event_type == "result":
                        stats = event.get("stats", {})
                        if not gemini_summary:
                            gemini_summary = {}

                        # Build summary in expected format matching Gemini's actual output
                        gemini_summary["stats"] = {
                            "models": {
                                model_name: {
                                    "api": {
                                        "totalRequests": 1,  # Simplified since stream doesn't provide turn count
                                        "totalLatencyMs": stats.get("duration_ms", 0)
                                    },
                                    "tokens": {
                                        # Use the actual field names from the stats
                                        "input": stats.get("input", 0),  # Input tokens excluding cache
                                        "prompt": stats.get("input_tokens", 0),  # Total input tokens
                                        "candidates": stats.get("output_tokens", 0),  # Output tokens
                                        "total": stats.get("total_tokens", 0),  # Total tokens
                                        "cached": stats.get("cached", 0)  # Cached tokens
                                    }
                                }
                            },
                            "tools": {
                                "totalCalls": stats.get("tool_calls", total_tool_calls),
                                "totalDurationMs": stats.get("duration_ms", 0),
                                "byName": {}
                            }
                        }

                        # Add tool counts
                        for tool_name, count in tool_counts.items():
                            gemini_summary["stats"]["tools"]["byName"][tool_name] = {"count": count}

                        break
                except json.JSONDecodeError:
                    continue

    # If we found a Gemini summary from stream, parse it
    if gemini_summary:
        return parse_gemini_json(gemini_summary)

    # Otherwise try to find standalone JSON summary (from json or text format)
    gemini_json_pattern = r'\{\s*"session_id"[^}]*?"stats"[^}]*?\}\s*\}\s*$'
    gemini_json_match = re.search(gemini_json_pattern, content, re.DOTALL | re.MULTILINE)
    if gemini_json_match:
        try:
            json_str = gemini_json_match.group(0)
            gemini_data = json.loads(json_str)
            return parse_gemini_json(gemini_data)
        except (json.JSONDecodeError, AttributeError) as e:
            # If regex fails, try to find JSON by looking for balanced braces
            start_idx = content.find('{\n  "session_id"')
            if start_idx >= 0:
                # Find the matching closing brace
                brace_count = 0
                in_string = False
                escape_next = False
                for i in range(start_idx, len(content)):
                    char = content[i]
                    if escape_next:
                        escape_next = False
                        continue
                    if char == '\\':
                        escape_next = True
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                try:
                                    json_str = content[start_idx:i+1]
                                    gemini_data = json.loads(json_str)
                                    return parse_gemini_json(gemini_data)
                                except json.JSONDecodeError:
                                    pass
                                break

    # Check for Cursor CLI output (detected by wrapper marker)
    if '[wrapper] Starting Cursor Agent...' in content:
        cursor_metrics = parse_cursor_json(content)
        if cursor_metrics:
            return cursor_metrics

    # Check for Codex JSONL format
    is_codex = False
    if '{"type":"thread.started"' in content or '{"type":"item.completed"' in content:
        is_codex = True
        # Parse Codex JSONL format
        codex_metrics = parse_codex_jsonl(content)
        if codex_metrics:
            return codex_metrics

    # Otherwise, parse as Claude's JSONL format
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Skip non-dict entries (e.g., JSON string literals)
        if not isinstance(entry, dict):
            continue

        event_type = entry.get("type", "")

        # Extract init info
        if event_type == "system" and entry.get("subtype") == "init":
            metrics["session_id"] = entry.get("session_id")
            metrics["claude_code_version"] = entry.get("claude_code_version")

        # Track tool usage from assistant messages
        if event_type == "assistant" and "message" in entry:
            message = entry.get("message", {})
            msg_content = message.get("content", [])
            usage = message.get("usage", {})

            # Accumulate per-message tokens for fallback (deduplicate by message ID)
            msg_id = message.get("id", "")
            if usage and msg_id:
                if "_seen_msg_ids" not in metrics:
                    metrics["_seen_msg_ids"] = set()
                if msg_id not in metrics["_seen_msg_ids"]:
                    metrics["_seen_msg_ids"].add(msg_id)
                    metrics["_acc_input"] = metrics.get("_acc_input", 0) + usage.get("input_tokens", 0)
                    metrics["_acc_output"] = metrics.get("_acc_output", 0) + usage.get("output_tokens", 0)
                    metrics["_acc_cache_read"] = metrics.get("_acc_cache_read", 0) + usage.get("cache_read_input_tokens", 0)
                    metrics["_acc_cache_create"] = metrics.get("_acc_cache_create", 0) + usage.get("cache_creation_input_tokens", 0)
                    metrics["_acc_turns"] = metrics.get("_acc_turns", 0) + 1

                    model_name = message.get("model", "unknown")
                    if "_acc_model_usage" not in metrics:
                        metrics["_acc_model_usage"] = {}
                    mu = metrics["_acc_model_usage"].setdefault(model_name, {
                        "inputTokens": 0, "outputTokens": 0,
                        "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0,
                        "costUSD": 0, "contextWindow": 200000,
                    })
                    mu["inputTokens"] += usage.get("input_tokens", 0)
                    mu["outputTokens"] += usage.get("output_tokens", 0)
                    mu["cacheReadInputTokens"] += usage.get("cache_read_input_tokens", 0)
                    mu["cacheCreationInputTokens"] += usage.get("cache_creation_input_tokens", 0)

            for item in msg_content:
                if item.get("type") == "tool_use":
                    tool_name = item.get("name", "")
                    tool_id = item.get("id", "")
                    tool_input = item.get("input", {})

                    # Track all tool usage
                    metrics["all_tools"][tool_name] = metrics["all_tools"].get(tool_name, 0) + 1

                    # Track MCP tools (any tool starting with mcp__)
                    if tool_name.startswith("mcp__"):
                        metrics["mcp_tools"]["total_calls"] += 1
                        metrics["mcp_tools"]["tools"][tool_name] = metrics["mcp_tools"]["tools"].get(tool_name, 0) + 1
                        metrics["mcp_tools"]["queries"].append({
                            "tool": tool_name,
                            "id": tool_id,
                            "input": tool_input,
                            "tokens": {
                                "input": usage.get("input_tokens", 0),
                                "output": usage.get("output_tokens", 0),
                            }
                        })

        # Extract final result metrics
        if event_type == "result":
            metrics["duration_seconds"] = entry.get("duration_ms", 0) / 1000
            metrics["duration_api_seconds"] = entry.get("duration_api_ms", 0) / 1000
            metrics["total_cost_usd"] = entry.get("total_cost_usd", 0)
            metrics["num_turns"] = entry.get("num_turns", 0)

            usage = entry.get("usage", {})
            metrics["tokens"]["input"] = usage.get("input_tokens", 0)
            metrics["tokens"]["output"] = usage.get("output_tokens", 0)
            metrics["tokens"]["cache_read"] = usage.get("cache_read_input_tokens", 0)
            metrics["tokens"]["cache_creation"] = usage.get("cache_creation_input_tokens", 0)

            metrics["model_usage"] = entry.get("modelUsage", {})

    # Fallback: if no 'result' entry, reconstruct from accumulated assistant messages
    if metrics["num_turns"] == 0 and metrics.get("_acc_turns", 0) > 0:
        metrics["num_turns"] = metrics["_acc_turns"]
        metrics["tokens"]["input"] = metrics.get("_acc_input", 0)
        metrics["tokens"]["output"] = metrics.get("_acc_output", 0)
        metrics["tokens"]["cache_read"] = metrics.get("_acc_cache_read", 0)
        metrics["tokens"]["cache_creation"] = metrics.get("_acc_cache_create", 0)
        metrics["model_usage"] = metrics.get("_acc_model_usage", {})

        for model_name, mu in metrics["model_usage"].items():
            if "opus" in model_name:
                mu["costUSD"] = (
                    (mu["inputTokens"] / 1_000_000) * 15.0
                    + (mu["outputTokens"] / 1_000_000) * 75.0
                    + (mu["cacheReadInputTokens"] / 1_000_000) * 1.5
                    + (mu["cacheCreationInputTokens"] / 1_000_000) * 18.75
                )
            elif "haiku" in model_name:
                mu["costUSD"] = (
                    (mu["inputTokens"] / 1_000_000) * 0.8
                    + (mu["outputTokens"] / 1_000_000) * 4.0
                    + (mu["cacheReadInputTokens"] / 1_000_000) * 0.08
                    + (mu["cacheCreationInputTokens"] / 1_000_000) * 1.0
                )
            elif "sonnet" in model_name:
                mu["costUSD"] = (
                    (mu["inputTokens"] / 1_000_000) * 3.0
                    + (mu["outputTokens"] / 1_000_000) * 15.0
                    + (mu["cacheReadInputTokens"] / 1_000_000) * 0.3
                    + (mu["cacheCreationInputTokens"] / 1_000_000) * 3.75
                )
        metrics["total_cost_usd"] = round(sum(
            mu.get("costUSD", 0) for mu in metrics["model_usage"].values()
        ), 4)

    # Clean up internal accumulator keys
    for key in list(metrics.keys()):
        if key.startswith("_acc") or key.startswith("_seen"):
            del metrics[key]

    return metrics


def _parse_pytest(fail_to_pass, vlog_text):
    """Parse pytest verification.log output.

    Handles both inline (test PASSED) and multi-line formats where PASSED/FAILED
    appears on a subsequent line.
    """
    outcomes = {}
    vlog_text = _strip_ansi(vlog_text)
    lines = vlog_text.splitlines()

    for ftp_test in fail_to_pass:
        found = False
        for i, line in enumerate(lines):
            if ftp_test in line:
                if " PASSED" in line:
                    outcomes[ftp_test] = "PASSED"
                    found = True
                    break
                elif " FAILED" in line:
                    outcomes[ftp_test] = "FAILED"
                    found = True
                    break
                elif " ERROR" in line:
                    outcomes[ftp_test] = "FAILED"
                    found = True
                    break
                else:
                    # PASSED/FAILED may be on a subsequent line
                    for j in range(i + 1, min(i + 11, len(lines))):
                        ahead = lines[j].strip()
                        if ahead == "PASSED" or ahead.startswith("PASSED "):
                            outcomes[ftp_test] = "PASSED"
                            found = True
                            break
                        elif ahead == "FAILED" or ahead.startswith("FAILED "):
                            outcomes[ftp_test] = "FAILED"
                            found = True
                            break
                        if "::" in ahead and (
                            " PASSED" in ahead or " FAILED" in ahead or
                            ahead.startswith("test/") or ahead.startswith("tests/")
                        ):
                            break
                    if found:
                        break

        if not found:
            # Check the short test summary info section for FAILED lines
            for line in lines:
                if line.startswith("FAILED ") and ftp_test in line:
                    outcomes[ftp_test] = "FAILED"
                    found = True
                    break
        if not found:
            outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


def _parse_go(fail_to_pass, vlog_text):
    """Parse Go test verification.log output.

    Matches: --- PASS: TestName (0.00s) / --- FAIL: TestName (0.05s)
    """
    outcomes = {}
    text = _strip_ansi(vlog_text)

    for ftp_test in fail_to_pass:
        escaped = re.escape(ftp_test)
        pattern = r'---\s+(PASS|FAIL):\s+' + escaped + r'[\s(/]'
        match = re.search(pattern, text)
        if match:
            result = match.group(1)
            outcomes[ftp_test] = "PASSED" if result == "PASS" else "FAILED"
        else:
            pattern2 = r'---\s+(PASS|FAIL):\s+' + escaped + r'\s*$'
            match2 = re.search(pattern2, text, re.MULTILINE)
            if match2:
                result = match2.group(1)
                outcomes[ftp_test] = "PASSED" if result == "PASS" else "FAILED"
            else:
                outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


def _parse_go_custom(fail_to_pass, vlog_text):
    """Parse Teleport's custom Go test runner verification.log.

    Handles:
      - "EXPECTED: Test function TestName does not exist yet"
      - Standard --- PASS/FAIL lines
    """
    outcomes = {}
    text = _strip_ansi(vlog_text)

    for ftp_test in fail_to_pass:
        escaped = re.escape(ftp_test)

        not_exist_pattern = r'EXPECTED: Test function ' + escaped + r' does not exist'
        if re.search(not_exist_pattern, text):
            outcomes[ftp_test] = "NOT_EXIST"
            continue

        pattern = r'---\s+(PASS|FAIL):\s+' + escaped + r'[\s(]'
        match = re.search(pattern, text)
        if match:
            result = match.group(1)
            outcomes[ftp_test] = "PASSED" if result == "PASS" else "FAILED"
        else:
            pattern2 = r'---\s+(PASS|FAIL):\s+' + escaped + r'\s*$'
            match2 = re.search(pattern2, text, re.MULTILINE)
            if match2:
                result = match2.group(1)
                outcomes[ftp_test] = "PASSED" if result == "PASS" else "FAILED"
            else:
                outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


def _parse_jest(fail_to_pass, vlog_text):
    """Parse Jest verification.log output (element-web).

    fail_to_pass format: "test/file.tsx | Suite Name | test description"
    """
    outcomes = {}
    vlog_text = _strip_ansi(vlog_text)

    for ftp_test in fail_to_pass:
        parts = [p.strip() for p in ftp_test.split(" | ")]
        file_path = parts[0] if parts else ""
        test_desc = parts[-1] if len(parts) > 1 else None

        if not test_desc:
            if re.search(r'^PASS\s+' + re.escape(file_path), vlog_text, re.MULTILINE):
                outcomes[ftp_test] = "PASSED"
            elif re.search(r'^FAIL\s+' + re.escape(file_path), vlog_text, re.MULTILINE):
                outcomes[ftp_test] = "FAILED"
            else:
                outcomes[ftp_test] = "NOT_FOUND"
            continue

        file_passed = bool(re.search(
            r'^PASS\s+' + re.escape(file_path), vlog_text, re.MULTILINE
        ))
        file_failed = bool(re.search(
            r'^FAIL\s+' + re.escape(file_path), vlog_text, re.MULTILINE
        ))

        if not file_passed and not file_failed:
            outcomes[ftp_test] = "NOT_FOUND"
            continue

        escaped_desc = re.escape(test_desc)
        pass_match = re.search(r'[✓✓]\s+' + escaped_desc, vlog_text)
        fail_match = re.search(r'[✕✗×]\s+' + escaped_desc, vlog_text)

        if pass_match and not fail_match:
            outcomes[ftp_test] = "PASSED"
        elif fail_match:
            outcomes[ftp_test] = "FAILED"
        elif file_passed:
            outcomes[ftp_test] = "PASSED"
        else:
            outcomes[ftp_test] = "FAILED"

    return outcomes


def _parse_jest_workspace(fail_to_pass, vlog_text):
    """Parse Jest workspace (webclients) verification.log.

    Uses "Running test:" / "Test execution completed/failed for" delimiters.
    """
    outcomes = {}
    vlog_text = _strip_ansi(vlog_text)

    for ftp_test in fail_to_pass:
        escaped = re.escape(ftp_test)

        completed = re.search(
            r'Test execution completed for\s+' + escaped, vlog_text
        )
        failed_msg = re.search(
            r'Test execution failed for\s+' + escaped, vlog_text
        )

        if completed and not failed_msg:
            outcomes[ftp_test] = "PASSED"
            continue
        if failed_msg:
            section_start = re.search(
                r'Running test:\s+' + escaped, vlog_text
            )
            if section_start:
                section_text = vlog_text[section_start.start():]
                next_test = re.search(r'\nRunning test:', section_text[1:])
                if next_test:
                    section_text = section_text[:next_test.start() + 1]
                if re.search(r'^PASS\s', section_text, re.MULTILINE):
                    outcomes[ftp_test] = "PASSED"
                    continue
            outcomes[ftp_test] = "FAILED"
            continue

        running = re.search(r'Running test:\s+' + escaped, vlog_text)
        if not running:
            outcomes[ftp_test] = "NOT_FOUND"
            continue

        section_start = running.start()
        section_text = vlog_text[section_start:]
        next_test = re.search(r'\nRunning test:', section_text[1:])
        if next_test:
            section_text = section_text[:next_test.start() + 1]

        if re.search(r'^PASS\s', section_text, re.MULTILINE):
            outcomes[ftp_test] = "PASSED"
        elif re.search(r'^FAIL\s', section_text, re.MULTILINE):
            outcomes[ftp_test] = "FAILED"
        else:
            skip_match = re.search(
                r'Tests:\s+(\d+)\s+skipped,\s+(\d+)\s+total', section_text
            )
            if skip_match and skip_match.group(1) == skip_match.group(2):
                outcomes[ftp_test] = "NOT_FOUND"
            else:
                outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


def _extract_mocha_json(text):
    """Extract the JSON object from NodeBB verification.log."""
    brace_depth = 0
    json_start = None
    json_end = None

    for i, ch in enumerate(text):
        if ch == '{' and json_start is None:
            lookahead = text[i:i + 50]
            if '"stats"' in lookahead:
                json_start = i
                brace_depth = 1
                continue
        if json_start is not None:
            if ch == '{':
                brace_depth += 1
            elif ch == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    json_end = i + 1
                    break

    if json_start is not None and json_end is not None:
        try:
            return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            return None
    return None


def _parse_mocha(fail_to_pass, vlog_text):
    """Parse Mocha (NodeBB) verification.log output.

    fail_to_pass format: "test/file.js | Suite Name | test description"
    JSON fullTitle format: "test/file.js::Suite ... title"
    """
    outcomes = {}
    vlog_text = _strip_ansi(vlog_text)
    json_data = _extract_mocha_json(vlog_text)

    if json_data:
        tests = json_data.get("tests", [])

        for ftp_test in fail_to_pass:
            parts = [p.strip() for p in ftp_test.split(" | ")]
            yaml_desc = parts[-1] if len(parts) > 1 else ftp_test

            found = False
            for t in tests:
                title = t.get("title", "")
                ft = t.get("fullTitle", "")

                if title and yaml_desc.endswith(title):
                    err = t.get("err", {})
                    if not err or err == {}:
                        outcomes[ftp_test] = "PASSED"
                    else:
                        outcomes[ftp_test] = "FAILED"
                    found = True
                    break
                if yaml_desc in ft:
                    err = t.get("err", {})
                    if not err or err == {}:
                        outcomes[ftp_test] = "PASSED"
                    else:
                        outcomes[ftp_test] = "FAILED"
                    found = True
                    break

            if not found:
                outcomes[ftp_test] = "NOT_FOUND"
    else:
        for ftp_test in fail_to_pass:
            parts = [p.strip() for p in ftp_test.split(" | ")]
            test_title = parts[-1] if parts else ftp_test
            escaped = re.escape(test_title)
            if re.search(r'[✓✔]\s+' + escaped, vlog_text):
                outcomes[ftp_test] = "PASSED"
            elif re.search(r'[✗✕]\s+' + escaped, vlog_text):
                outcomes[ftp_test] = "FAILED"
            elif re.search(r'\d+\)\s+' + escaped, vlog_text):
                outcomes[ftp_test] = "FAILED"
            else:
                outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


def _parse_custom_tutanota(fail_to_pass, vlog_text):
    """Parse Tutanota's custom test runner verification.log.

    Checks for "All N assertions passed" or "N out of M assertions failed".
    """
    outcomes = {}
    vlog_text = _strip_ansi(vlog_text)

    all_passed = re.search(r'All\s+\d+\s+assertions?\s+passed', vlog_text)
    some_failed = re.search(
        r'(\d+)\s+out of\s+(\d+)\s+assertions?\s+failed', vlog_text
    )

    if all_passed and not some_failed:
        for ftp_test in fail_to_pass:
            outcomes[ftp_test] = "PASSED"
    elif some_failed:
        for ftp_test in fail_to_pass:
            outcomes[ftp_test] = "FAILED"
    else:
        if "Build failed" in vlog_text or "Error:" in vlog_text[:500]:
            for ftp_test in fail_to_pass:
                outcomes[ftp_test] = "FAILED"
        else:
            for ftp_test in fail_to_pass:
                outcomes[ftp_test] = "NOT_FOUND"

    return outcomes


_FRAMEWORK_PARSERS = {
    "pytest": _parse_pytest,
    "go": _parse_go,
    "go_custom": _parse_go_custom,
    "jest": _parse_jest,
    "jest_workspace": _parse_jest_workspace,
    "mocha": _parse_mocha,
    "custom": _parse_custom_tutanota,
}


def parse_verification_log(verification_log_path, fail_to_pass=None, repo_name=""):
    """Extract test results from verification log using framework-aware parsers.

    When fail_to_pass list and repo_name are provided, uses the proven parsers
    from audit_artifacts.py to determine exact per-test outcomes. Falls back to
    legacy regex parsing when these are not available.
    """
    results = {
        "tests_total": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "fail_to_pass_results": {},
        "pass_to_pass_results": {},
        "test_output_summary": "",
        "test_framework": "unknown"
    }

    if not os.path.exists(verification_log_path):
        return results

    with open(verification_log_path, "r", errors="replace") as f:
        content = f.read()

    # Extract summary from last few lines
    lines = content.strip().split("\n")
    if lines:
        results["test_output_summary"] = "\n".join(lines[-10:])

    # --- Framework-aware path (preferred) ---
    if fail_to_pass and repo_name:
        framework = _get_framework_for_repo(repo_name)
        results["test_framework"] = framework

        parser = _FRAMEWORK_PARSERS.get(framework)
        if parser:
            outcomes = parser(fail_to_pass, content)
        else:
            outcomes = {t: "NOT_FOUND" for t in fail_to_pass}

        passed = [t for t, o in outcomes.items() if o == "PASSED"]
        failed = [t for t, o in outcomes.items()
                  if o in ("FAILED", "NOT_FOUND", "NOT_EXIST")]

        results["tests_total"] = len(fail_to_pass)
        results["tests_passed"] = len(passed)
        results["tests_failed"] = len(failed)

        for t, o in outcomes.items():
            results["fail_to_pass_results"][t] = "PASS" if o == "PASSED" else "FAIL"

        return results

    # --- Legacy fallback (no fail_to_pass or repo_name) ---
    all_passed_tests = []
    all_failed_tests = []
    all_skipped_tests = []

    # 1. PYTEST FORMAT
    pytest_pass_pattern = r'(test/.*?\.py::[^\s]+)\s+PASSED'
    pytest_fail_pattern = r'(test/.*?\.py::[^\s]+)\s+FAILED'
    pytest_skip_pattern = r'(test/.*?\.py::[^\s]+)\s+SKIPPED'
    pytest_error_pattern = r'(test/.*?\.py::[^\s]+)\s+ERROR'

    pytest_passes = re.findall(pytest_pass_pattern, content)
    pytest_fails = re.findall(pytest_fail_pattern, content)
    pytest_skips = re.findall(pytest_skip_pattern, content)
    pytest_errors = re.findall(pytest_error_pattern, content)

    if pytest_passes or pytest_fails or pytest_skips or pytest_errors:
        results["test_framework"] = "pytest"
        all_passed_tests.extend(pytest_passes)
        all_failed_tests.extend(pytest_fails)
        all_skipped_tests.extend(pytest_skips)
        all_failed_tests.extend(pytest_errors)
    else:
        ansible_pass_pattern = r'\[gw\d+\].*?\[\s*\d+%\].*?PASSED.*?(test/units/[^\s]+(?:::[^\s\]]+)*)'
        ansible_fail_pattern = r'\[gw\d+\].*?\[\s*\d+%\].*?FAILED.*?(test/units/[^\s]+(?:::[^\s\]]+)*)'
        ansible_skip_pattern = r'\[gw\d+\].*?\[\s*\d+%\].*?SKIPPED.*?(test/units/[^\s]+(?:::[^\s\]]+)*)'
        ansible_error_pattern = r'\[gw\d+\].*?\[\s*\d+%\].*?ERROR.*?(test/units/[^\s]+(?:::[^\s\]]+)*)'

        ansible_passes = re.findall(ansible_pass_pattern, content)
        ansible_fails = re.findall(ansible_fail_pattern, content)
        ansible_skips = re.findall(ansible_skip_pattern, content)
        ansible_errors = re.findall(ansible_error_pattern, content)

        if ansible_passes or ansible_fails or ansible_skips or ansible_errors:
            results["test_framework"] = "pytest-ansible"
            all_passed_tests.extend(ansible_passes)
            all_failed_tests.extend(ansible_fails)
            all_skipped_tests.extend(ansible_skips)
            all_failed_tests.extend(ansible_errors)

    # 2. GO TEST FORMAT
    if not all_passed_tests and not all_failed_tests:
        go_pass_pattern = r"---\s+PASS:\s+(\S+)"
        go_fail_pattern = r"---\s+FAIL:\s+(\S+)"

        go_passes = re.findall(go_pass_pattern, content)
        go_fails = re.findall(go_fail_pattern, content)

        if go_passes or go_fails:
            results["test_framework"] = "go"
            all_passed_tests.extend(go_passes)
            all_failed_tests.extend(go_fails)

    # 3. JEST/MOCHA FORMAT
    if not all_passed_tests and not all_failed_tests:
        jest_pass_pattern = r"PASS\s+([\S]+\.(?:js|jsx|ts|tsx))"
        jest_fail_pattern = r"FAIL\s+([\S]+\.(?:js|jsx|ts|tsx))"

        jest_passes = re.findall(jest_pass_pattern, content)
        jest_fails = re.findall(jest_fail_pattern, content)

        if jest_passes or jest_fails:
            results["test_framework"] = "jest"
            all_passed_tests.extend(jest_passes)
            all_failed_tests.extend(jest_fails)

    # 4. SUMMARY PATTERNS
    if not all_passed_tests and not all_failed_tests:
        summary_patterns = [
            (r"=+\s*(\d+)\s+passed(?:,\s*(\d+)\s+failed)?.*=+", "pytest"),
            (r"Tests?:\s*(\d+)\s+passed(?:,\s*(\d+)\s+failed)?,\s*\d+\s+total", "jest"),
            (r"(?:PASS|ok)\s+\S+\s+[\d.]+s", "go"),
            (r"(\d+)\s+test(?:s)?\s+passed", "generic"),
        ]

        for pattern, framework in summary_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                if results["test_framework"] == "unknown":
                    results["test_framework"] = framework
                if framework in ["pytest", "jest"]:
                    passed_count = int(match.group(1)) if match.group(1) else 0
                    failed_count = int(match.group(2)) if len(match.groups()) > 1 and match.group(2) else 0
                    for i in range(passed_count):
                        all_passed_tests.append(f"test_{i+1}")
                    for i in range(failed_count):
                        all_failed_tests.append(f"failed_test_{i+1}")
                elif framework == "go" and "PASS" in match.group(0):
                    all_passed_tests.append("tests")
                break

    all_passed_tests = list(dict.fromkeys(all_passed_tests))
    all_failed_tests = list(dict.fromkeys(all_failed_tests))
    all_skipped_tests = list(dict.fromkeys(all_skipped_tests))

    results["tests_passed"] = len(all_passed_tests)
    results["tests_failed"] = len(all_failed_tests)
    results["tests_total"] = results["tests_passed"] + results["tests_failed"] + len(all_skipped_tests)

    for test in all_passed_tests:
        results["fail_to_pass_results"][test] = "PASS"
    for test in all_failed_tests:
        results["fail_to_pass_results"][test] = "FAIL"

    return results


def parse_patch(patch_path: str) -> dict:
    """Extract code change metrics from git diff patch."""
    metrics = {
        "lines_added": 0,
        "lines_removed": 0,
        "lines_changed": 0,
        "files_modified": 0,
        "files": [],
    }

    if not os.path.exists(patch_path):
        print(f"[metrics] DEBUG: Patch file not found at {patch_path}")
        # List contents of parent directory for debugging
        parent_dir = os.path.dirname(patch_path)
        if os.path.exists(parent_dir):
            print(f"[metrics] DEBUG: Contents of {parent_dir}:")
            for item in os.listdir(parent_dir):
                print(f"[metrics] DEBUG:   - {item}")
        return metrics

    with open(patch_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    print(f"[metrics] DEBUG: Patch file found with {len(content)} bytes")

    # Count files modified
    file_pattern = r"^diff --git a/(\S+)"
    files = re.findall(file_pattern, content, re.MULTILINE)
    metrics["files_modified"] = len(files)
    metrics["files"] = files

    if len(files) > 0:
        print(f"[metrics] DEBUG: Found {len(files)} modified files in patch")

    # Count lines added/removed
    for line in content.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            metrics["lines_added"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            metrics["lines_removed"] += 1

    metrics["lines_changed"] = metrics["lines_added"] + metrics["lines_removed"]

    return metrics


def main():
    """Generate enhanced result.json with all metrics."""
    results_dir = os.environ.get("RESULTS_DIR", "/results")

    # Get basic info from environment
    task_id = os.environ.get("TASK_ID", "unknown")
    model = os.environ.get("MODEL", "unknown")
    mcp_enabled = os.environ.get("MCP_CONFIG", "") != ""
    agent_exit = int(os.environ.get("AGENT_EXIT_CODE", "1"))
    verify_exit = int(os.environ.get("VERIFY_EXIT_CODE", "1"))

    # Load fail_to_pass list from file (set by workflow)
    fail_to_pass_file = os.environ.get("FAIL_TO_PASS_FILE", "")
    fail_to_pass = []
    if fail_to_pass_file and os.path.exists(fail_to_pass_file):
        with open(fail_to_pass_file) as f:
            fail_to_pass = [line.strip() for line in f if line.strip()]
        print(f"[metrics] Loaded {len(fail_to_pass)} fail_to_pass tests from {fail_to_pass_file}")

    repo_name = os.environ.get("REPO_NAME", "")

    # Load pass_to_pass list from file (set by workflow)
    pass_to_pass_file = os.environ.get("PASS_TO_PASS_FILE", "")
    pass_to_pass = []
    if pass_to_pass_file and os.path.exists(pass_to_pass_file):
        with open(pass_to_pass_file) as f:
            pass_to_pass = [line.strip() for line in f if line.strip()]
        print(f"[metrics] Loaded {len(pass_to_pass)} pass_to_pass tests from {pass_to_pass_file}")

    # Determine status — exit-code based (original), may be overridden below
    exit_code_resolved = verify_exit == 0
    resolved = exit_code_resolved

    # Parse all metrics sources
    trajectory_metrics = parse_trajectory(f"{results_dir}/agent.log")
    test_results = parse_verification_log(
        f"{results_dir}/verification.log", fail_to_pass, repo_name
    )

    # Parse P2P verification log (post-patch)
    p2p_results = parse_verification_log(
        f"{results_dir}/p2p_verification.log", pass_to_pass, repo_name
    )

    # Determine P2P regression status
    p2p_no_regression = True
    if pass_to_pass:
        if p2p_results["tests_failed"] > 0:
            p2p_no_regression = False
        elif p2p_results["tests_passed"] == 0 and p2p_results["tests_total"] > 0:
            p2p_no_regression = False  # Couldn't verify

    # Override resolved using actual test outcomes when fail_to_pass is available
    f2p_resolved = exit_code_resolved  # default fallback
    if fail_to_pass and test_results["test_framework"] != "unknown":
        f2p_resolved = (test_results["tests_failed"] == 0 and test_results["tests_passed"] > 0)
        fully_resolved = f2p_resolved and p2p_no_regression
        resolved = fully_resolved
    elif test_results["tests_failed"] > 0:
        f2p_resolved = False
        resolved = False
        # else: no tests found at all — keep exit_code_resolved as fallback

    status = "success" if resolved else "failed"

    # Debug: Check if patch file exists
    patch_path = f"{results_dir}/changes.patch"
    print(f"[metrics] DEBUG: Checking for patch at: {patch_path}")
    if os.path.exists(patch_path):
        stat = os.stat(patch_path)
        print(f"[metrics] DEBUG: Patch file exists, size: {stat.st_size} bytes")
    else:
        print(f"[metrics] DEBUG: Patch file does NOT exist at {patch_path}")

    patch_metrics = parse_patch(patch_path)

    # Build enhanced result
    result = {
        # Standard SWE-bench fields
        "task": task_id,
        "status": status,
        "resolved": resolved,
        "f2p_resolved": f2p_resolved,
        "p2p_no_regression": p2p_no_regression,
        "model": model,
        "mcp_enabled": mcp_enabled,

        # Exit codes
        "agent_exit_code": agent_exit,
        "verification_exit_code": verify_exit,
        "exit_code_resolved": exit_code_resolved,

        # Test results
        "tests": {
            "total": test_results["tests_total"],
            "passed": test_results["tests_passed"],
            "failed": test_results["tests_failed"],
        },
        "fail_to_pass_results": test_results["fail_to_pass_results"],
        "pass_to_pass_results": p2p_results["fail_to_pass_results"],
        "p2p_tests": {
            "total": p2p_results["tests_total"],
            "passed": p2p_results["tests_passed"],
            "failed": p2p_results["tests_failed"],
        },

        # Agent metrics (from trajectory)
        "duration_seconds": trajectory_metrics["duration_seconds"],
        "duration_api_seconds": trajectory_metrics["duration_api_seconds"],
        "total_cost_usd": trajectory_metrics["total_cost_usd"],
        "num_turns": trajectory_metrics["num_turns"],
        "tokens": trajectory_metrics["tokens"],

        # Code change metrics
        "code_changes": {
            "lines_added": patch_metrics["lines_added"],
            "lines_removed": patch_metrics["lines_removed"],
            "lines_changed": patch_metrics["lines_changed"],
            "files_modified": patch_metrics["files_modified"],
            "files": patch_metrics["files"],
        },

        # Metadata
        "session_id": trajectory_metrics["session_id"],
        "claude_code_version": trajectory_metrics["claude_code_version"],
        "timestamp": os.environ.get("TIMESTAMP", ""),

        # Cost model (per-token for Claude/Codex/Gemini, subscription for Cursor)
        "cost_model": trajectory_metrics.get("cost_model", "per_token"),

        # Model breakdown (for cost attribution)
        "model_usage": trajectory_metrics["model_usage"],

        # Tool usage breakdown (for A/B test analysis)
        "tool_usage": {
            "all_tools": trajectory_metrics["all_tools"],
            "total_tool_calls": sum(trajectory_metrics["all_tools"].values()),
            "mcp_tools": trajectory_metrics["mcp_tools"],
        },
    }

    # Write enhanced result
    output_path = f"{results_dir}/result.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"[metrics] Enhanced result written to {output_path}")
    print(f"[metrics] Status: {status}")
    print(f"[metrics] F2P Tests: {test_results['tests_passed']}/{test_results['tests_total']} passed")
    if pass_to_pass:
        print(f"[metrics] P2P Tests: {p2p_results['tests_passed']}/{p2p_results['tests_total']} passed")
        print(f"[metrics] P2P No Regression: {p2p_no_regression}")
    else:
        print(f"[metrics] P2P Tests: none (no pass_to_pass tests for this task)")
    print(f"[metrics] Cost: ${trajectory_metrics['total_cost_usd']:.4f}")
    print(f"[metrics] Duration: {trajectory_metrics['duration_seconds']:.1f}s")
    print(f"[metrics] Code changes: {patch_metrics['lines_changed']} lines in {patch_metrics['files_modified']} files")
    print(f"[metrics] Total tool calls: {sum(trajectory_metrics['all_tools'].values())}")
    print(f"[metrics] MCP tool calls: {trajectory_metrics['mcp_tools']['total_calls']}")
    if trajectory_metrics['mcp_tools']['tools']:
        print(f"[metrics] MCP tools used: {trajectory_metrics['mcp_tools']['tools']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
