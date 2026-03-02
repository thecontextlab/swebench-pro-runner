"""Shared utilities for SWE-bench Pro evaluation scripts.

Common functions for parsing folder names, loading results, extracting metrics,
and scanning agent logs across Claude and Codex result formats.
"""

import json
import os

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# All supported repositories
REPOS = [
    "ansible", "element-web", "flipt", "navidrome", "NodeBB",
    "openlibrary", "qutebrowser", "teleport", "tutanota", "vuls", "webclients",
]

# GitHub org (from task_id) → dataset repo name
ORG_TO_REPO = {
    "ansible": "ansible",
    "element-hq": "element-web",
    "flipt-io": "flipt",
    "navidrome": "navidrome",
    "NodeBB": "NodeBB",
    "internetarchive": "openlibrary",
    "qutebrowser": "qutebrowser",
    "gravitational": "teleport",
    "tutao": "tutanota",
    "future-architect": "vuls",
    "protonmail": "webclients",
}

# Test framework classification by repo
PYTEST_REPOS = {"ansible", "openlibrary", "qutebrowser"}
GO_REPOS = {"vuls", "flipt", "navidrome"}
GO_CUSTOM_REPOS = {"teleport"}
JEST_REPOS = {"element-web"}
JEST_WORKSPACE_REPOS = {"webclients"}
MOCHA_REPOS = {"NodeBB"}
CUSTOM_REPOS = {"tutanota"}

# Multi-word repo names that must be matched before splitting on dash
_MULTI_WORD_REPOS = [r for r in REPOS if "-" in r]  # ["element-web"]


def get_repo_from_folder(folder):
    """Extract repo name from folder like 'codex-gpt52-{repo}-{hash}' or 'claude-opus-4-6-{repo}-{hash}'.

    Strips known prefixes, then matches against the known repo list.
    Multi-word repos (element-web) are checked first to avoid splitting errors.
    """
    name = folder
    # Strip known model prefixes
    for prefix in ("codex-gpt52-", "claude-opus-4-6-", "claude-sonnet-4-5-",
                   "claude-sonnet-4-", "claude-haiku-4-5-"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    # Match multi-word repos first, then single-word
    for r in _MULTI_WORD_REPOS:
        if name.startswith(r + "-"):
            return r
    for r in REPOS:
        if name.startswith(r + "-"):
            return r
    return name.split("-")[0]


def get_hash_part(folder):
    """Extract the task hash identifier from folder name.

    E.g. 'codex-gpt52-vuls-abc123def' -> 'abc123def'
    """
    name = folder
    for prefix in ("codex-gpt52-", "claude-opus-4-6-", "claude-sonnet-4-5-",
                   "claude-sonnet-4-", "claude-haiku-4-5-"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    repo = get_repo_from_folder(folder)
    if name.startswith(repo + "-"):
        return name[len(repo) + 1:]
    return name


def load_result(folder_path):
    """Load result.json from an artifact folder. Returns dict or None."""
    if not folder_path:
        return None
    rj_path = os.path.join(folder_path, "result.json")
    if not os.path.exists(rj_path):
        return None
    try:
        with open(rj_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_task_id(data):
    """Get task identifier from result.json, handling Claude ('task_id') and Codex ('task') formats."""
    if not data:
        return ""
    return data.get("task_id", "") or data.get("task", "")


def extract_metrics(data):
    """Normalize metrics across Claude/Codex result.json formats.

    Handles:
    - Claude: tokens.input, tokens.output, tokens.cache_read, tool_usage.all_tools
    - Codex: tokens.input, tokens.output, tool_usage.total_tool_calls
    """
    if not data:
        return _empty_metrics()

    tokens = data.get("tokens", {})
    tool_usage = data.get("tool_usage", {})

    return {
        "resolved": data.get("resolved", False),
        "duration_seconds": data.get("duration_seconds", 0),
        "duration_api_seconds": data.get("duration_api_seconds", 0),
        "total_cost_usd": data.get("total_cost_usd", 0),
        "tokens_input": tokens.get("input", 0),
        "tokens_output": tokens.get("output", 0),
        "tokens_cache_read": tokens.get("cache_read", 0),
        "tokens_cache_creation": tokens.get("cache_creation", 0),
        "total_tool_calls": tool_usage.get("total_tool_calls", 0),
        "num_turns": data.get("num_turns", 0),
        "all_tools": tool_usage.get("all_tools", {}),
        "model": data.get("model", "unknown"),
    }


def _empty_metrics():
    return {
        "resolved": False, "duration_seconds": 0, "duration_api_seconds": 0,
        "total_cost_usd": 0, "tokens_input": 0, "tokens_output": 0,
        "tokens_cache_read": 0, "tokens_cache_creation": 0,
        "total_tool_calls": 0, "num_turns": 0, "all_tools": {}, "model": "unknown",
    }


def scan_agent_log(log_path):
    """Scan agent.log for rate limiting and turn.failed events.

    Returns dict with boolean flags:
      {"rate_limited": bool, "turn_failed": bool}
    """
    result = {"rate_limited": False, "turn_failed": False}
    if not log_path or not os.path.exists(log_path):
        return result
    try:
        with open(log_path, "r", errors="replace") as f:
            for line in f:
                lower = line.lower()
                if "rate_limit" in lower:
                    result["rate_limited"] = True
                if "turn.failed" in line:
                    result["turn_failed"] = True
                if result["rate_limited"] and result["turn_failed"]:
                    break
    except OSError:
        pass
    return result


def parse_display_title(title):
    """Parse GHA displayTitle 'repo | task_id | agent | MCP:flag' into components.

    Returns dict with keys: repo, task_id, agent, mcp (or None values on parse failure).
    """
    parts = [p.strip() for p in title.split("|")]
    if len(parts) >= 4:
        mcp_raw = parts[3].replace("MCP:", "").strip().lower()
        return {
            "repo": parts[0],
            "task_id": parts[1],
            "agent": parts[2],
            "mcp": mcp_raw == "true",
        }
    return {"repo": None, "task_id": None, "agent": None, "mcp": None}


def index_artifact_dir(directory):
    """Index an artifact directory into {hash_part: full_path} mapping."""
    result = {}
    if not os.path.exists(directory):
        return result
    for name in os.listdir(directory):
        full = os.path.join(directory, name)
        if os.path.isdir(full):
            hp = get_hash_part(name)
            result[hp] = full
    return result


def get_repo_from_task_id(task_id):
    """Map task_id like 'ansible__ansible-abc123' to repo name 'ansible'.

    Extracts the org prefix before '__' and looks up in ORG_TO_REPO.
    """
    if "__" not in task_id:
        return None
    org = task_id.split("__")[0]
    return ORG_TO_REPO.get(org)


def get_framework_for_repo(repo):
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


def _load_fail_to_pass_manual(yaml_path):
    """Extract swebench.fail_to_pass list from task YAML without PyYAML.

    Handles simple YAML list format under swebench.fail_to_pass key.
    Supports both unquoted and quoted string entries.
    """
    with open(yaml_path) as f:
        lines = f.readlines()

    in_swebench = False
    in_ftp = False
    ftp_list = []
    for line in lines:
        stripped = line.strip()
        rstripped = line.rstrip()
        indent = len(rstripped) - len(rstripped.lstrip())

        if stripped == "swebench:":
            in_swebench = True
            continue
        if in_swebench and not in_ftp:
            if stripped == "fail_to_pass:" or stripped == "fail_to_pass: []":
                if stripped == "fail_to_pass: []":
                    return []
                in_ftp = True
                continue
            # If we hit a non-indented line, we left the swebench block
            if indent == 0 and stripped and not stripped.startswith("#"):
                in_swebench = False
        if in_ftp:
            if stripped.startswith("- "):
                entry = stripped[2:].strip()
                # Remove surrounding quotes
                if (entry.startswith("'") and entry.endswith("'")) or \
                   (entry.startswith('"') and entry.endswith('"')):
                    entry = entry[1:-1]
                ftp_list.append(entry)
            elif stripped and not stripped.startswith("#") and not stripped.startswith("- "):
                break  # End of fail_to_pass list
    return ftp_list


def load_task_yaml(task_yaml_dir, task_id):
    """Load fail_to_pass list from task YAML file.

    Args:
        task_yaml_dir: Root datasets directory (e.g. /path/to/eval-runner/datasets)
        task_id: Full task identifier (e.g. 'ansible__ansible-abc123-vdef456')

    Returns:
        List of fail_to_pass test identifiers, or None if YAML not found.
    """
    repo = get_repo_from_task_id(task_id)
    if not repo:
        return None
    yaml_path = os.path.join(task_yaml_dir, repo, "tasks", f"{task_id}.yaml")
    if not os.path.exists(yaml_path):
        return None

    if HAS_YAML:
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
            return data.get("swebench", {}).get("fail_to_pass", [])
        except Exception:
            return _load_fail_to_pass_manual(yaml_path)
    else:
        return _load_fail_to_pass_manual(yaml_path)


def _load_pass_to_pass_manual(yaml_path):
    """Extract swebench.pass_to_pass list from task YAML without PyYAML.

    Same approach as _load_fail_to_pass_manual but for the pass_to_pass key.
    """
    with open(yaml_path) as f:
        lines = f.readlines()

    in_swebench = False
    in_ptp = False
    ptp_list = []
    for line in lines:
        stripped = line.strip()
        rstripped = line.rstrip()
        indent = len(rstripped) - len(rstripped.lstrip())

        if stripped == "swebench:":
            in_swebench = True
            continue
        if in_swebench and not in_ptp:
            if stripped == "pass_to_pass:" or stripped == "pass_to_pass: []":
                if stripped == "pass_to_pass: []":
                    return []
                in_ptp = True
                continue
            if indent == 0 and stripped and not stripped.startswith("#"):
                in_swebench = False
        if in_ptp:
            if stripped.startswith("- "):
                entry = stripped[2:].strip()
                if (entry.startswith("'") and entry.endswith("'")) or \
                   (entry.startswith('"') and entry.endswith('"')):
                    entry = entry[1:-1]
                ptp_list.append(entry)
            elif stripped and not stripped.startswith("#") and not stripped.startswith("- "):
                break  # End of pass_to_pass list
    return ptp_list


def load_pass_to_pass(task_yaml_dir, task_id):
    """Load pass_to_pass list from task YAML file.

    Args:
        task_yaml_dir: Root datasets directory (e.g. /path/to/eval-runner/datasets)
        task_id: Full task identifier (e.g. 'ansible__ansible-abc123-vdef456')

    Returns:
        List of pass_to_pass test identifiers, or None if YAML not found.
        Returns empty list if the task has no pass_to_pass tests.
    """
    repo = get_repo_from_task_id(task_id)
    if not repo:
        return None
    yaml_path = os.path.join(task_yaml_dir, repo, "tasks", f"{task_id}.yaml")
    if not os.path.exists(yaml_path):
        return None

    if HAS_YAML:
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
            return data.get("swebench", {}).get("pass_to_pass", [])
        except Exception:
            return _load_pass_to_pass_manual(yaml_path)
    else:
        return _load_pass_to_pass_manual(yaml_path)
