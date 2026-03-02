#!/usr/bin/env python3
"""Download SWE-bench Pro evaluation artifacts from GitHub Actions.

Replaces: download_100_task_artifacts.sh, download_artifacts_20260216.sh,
download_experiment_artifacts.sh, and ~10 other download scripts.

Fetches completed workflow runs, filters by date/model/agent/MCP, downloads
artifacts, and organizes them into flat per-task directories.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime


def run_gh(args, capture=True):
    """Run a gh CLI command. Returns stdout string or raises on failure."""
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0:
        print(f"Error running: {' '.join(cmd)}", file=sys.stderr)
        if capture:
            print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout if capture else ""


def fetch_runs(limit, cache_path=None):
    """Fetch workflow runs from GitHub Actions. Uses cache if available."""
    if cache_path and os.path.exists(cache_path):
        with open(cache_path) as f:
            return json.load(f)

    print(f"Fetching up to {limit} runs from GitHub Actions...")
    stdout = run_gh([
        "run", "list", "--workflow=swebench-eval.yml",
        f"--limit={limit}",
        "--json", "databaseId,displayTitle,status,conclusion,createdAt",
    ])
    runs = json.loads(stdout)

    if cache_path:
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(runs, f)
        print(f"Cached {len(runs)} runs to {cache_path}")

    return runs


def filter_runs(runs, start_date=None, end_date=None, model=None, agent=None,
                mcp=None, status="completed", conclusion="success"):
    """Filter runs by various criteria based on displayTitle and metadata."""
    filtered = []
    for run in runs:
        # Status/conclusion filter
        if status and run.get("status") != status:
            continue
        if conclusion and run.get("conclusion") != conclusion:
            continue

        # Date filter
        created = run.get("createdAt", "")
        if start_date and created < start_date:
            continue
        if end_date and created > end_date + "T99":  # end of day
            continue

        title = run.get("displayTitle", "")

        # Model filter (check displayTitle contains the model string)
        if model and model not in title:
            continue

        # Agent filter
        if agent and f"| {agent} |" not in title and f"| {agent}" not in title:
            continue

        # MCP filter
        if mcp is not None:
            mcp_str = f"MCP:{str(mcp).lower()}"
            if mcp_str not in title.lower():
                continue

        filtered.append(run)

    return filtered


def download_artifact(run_id, temp_dir):
    """Download swebench-result artifacts for a run."""
    try:
        subprocess.run(
            ["gh", "run", "download", str(run_id),
             "--pattern=swebench-result-*", f"--dir={temp_dir}"],
            capture_output=True, text=True, timeout=120,
        )
        return True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


def flatten_artifact(temp_dir, output_dir, folder_prefix):
    """Move artifact files from nested GHA structure to flat output folder.

    GHA creates: temp_dir/swebench-result-{ID}/result.json, agent.log, ...
    We want:     output_dir/{prefix}-{repo}-{hash}/result.json, agent.log, ...
    """
    # Find the swebench-result-* subdirectory
    subdirs = [d for d in os.listdir(temp_dir) if d.startswith("swebench-result-")]
    if not subdirs:
        return None

    src_dir = os.path.join(temp_dir, subdirs[0])
    if not os.path.isdir(src_dir):
        return None

    # Read result.json to extract task info for folder naming
    result_path = os.path.join(src_dir, "result.json")
    if not os.path.exists(result_path):
        return None

    try:
        with open(result_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    # Build folder name from task_id
    task_id = data.get("task_id", "")
    if not task_id:
        return None

    # Parse task_id: "org__repo-hash" -> repo, hash
    parts = task_id.split("__")
    if len(parts) >= 2:
        repo_and_hash = parts[1]
        # Fix element-web double-web naming
        repo_and_hash = repo_and_hash.replace("element-web-web-", "element-web-")
    else:
        repo_and_hash = task_id

    folder_name = f"{folder_prefix}-{repo_and_hash}" if folder_prefix else repo_and_hash
    dest_dir = os.path.join(output_dir, folder_name)

    if os.path.exists(dest_dir):
        return dest_dir  # Already exists, skip

    os.makedirs(dest_dir, exist_ok=True)
    for fname in os.listdir(src_dir):
        src = os.path.join(src_dir, fname)
        dst = os.path.join(dest_dir, fname)
        if os.path.isfile(src):
            shutil.copy2(src, dst)

    return dest_dir


def main():
    parser = argparse.ArgumentParser(
        description="Download SWE-bench Pro artifacts from GitHub Actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Download Codex gpt-5.2 baseline runs from Feb 20
  python3 download_artifacts.py --start-date 2026-02-20 --model gpt-5.2-codex \\
    --agent codex --mcp false --output-dir ./eval-codex52 --folder-prefix codex-gpt52

  # Download Claude opus runs with MCP enabled
  python3 download_artifacts.py --start-date 2026-02-18 --model claude-opus-4-6 \\
    --mcp true --output-dir ./eval-opus46-mcp --folder-prefix claude-opus-4-6
""",
    )
    parser.add_argument("--start-date", help="Filter runs created on/after this date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Filter runs created on/before this date (YYYY-MM-DD)")
    parser.add_argument("--model", help="Filter by model string in displayTitle")
    parser.add_argument("--agent", help="Filter by agent name (claude, codex, etc)")
    parser.add_argument("--mcp", choices=["true", "false"], help="Filter by MCP enabled/disabled")
    parser.add_argument("--output-dir", required=True, help="Directory to store downloaded artifacts")
    parser.add_argument("--folder-prefix", default="", help="Prefix for artifact folder names (e.g. codex-gpt52)")
    parser.add_argument("--limit", type=int, default=500, help="Max runs to fetch from GHA (default: 500)")
    parser.add_argument("--cache-file", help="Path to cache GHA run list JSON (avoids repeated API calls)")
    parser.add_argument("--status", default="completed", help="Run status filter (default: completed)")
    parser.add_argument("--conclusion", default="success", help="Run conclusion filter (default: success)")
    args = parser.parse_args()

    mcp_bool = None
    if args.mcp is not None:
        mcp_bool = args.mcp == "true"

    # Fetch and filter runs
    runs = fetch_runs(args.limit, args.cache_file)
    print(f"Total runs fetched: {len(runs)}")

    filtered = filter_runs(
        runs,
        start_date=args.start_date,
        end_date=args.end_date,
        model=args.model,
        agent=args.agent,
        mcp=mcp_bool,
        status=args.status,
        conclusion=args.conclusion,
    )
    print(f"Runs matching filters: {len(filtered)}")

    if not filtered:
        print("No matching runs found.")
        return

    os.makedirs(args.output_dir, exist_ok=True)

    # Track what we already have (idempotent)
    existing = set()
    if os.path.exists(args.output_dir):
        existing = set(os.listdir(args.output_dir))

    downloaded = 0
    skipped = 0
    failed = 0

    for i, run in enumerate(filtered):
        run_id = run["databaseId"]
        title = run.get("displayTitle", "")
        print(f"\n[{i+1}/{len(filtered)}] Run {run_id}: {title}")

        with tempfile.TemporaryDirectory() as tmp:
            if not download_artifact(run_id, tmp):
                print(f"  FAILED to download")
                failed += 1
                continue

            dest = flatten_artifact(tmp, args.output_dir, args.folder_prefix)
            if dest is None:
                print(f"  FAILED to extract artifact")
                failed += 1
                continue

            folder_name = os.path.basename(dest)
            if folder_name in existing:
                print(f"  SKIPPED (already exists): {folder_name}")
                skipped += 1
            else:
                print(f"  Downloaded: {folder_name}")
                existing.add(folder_name)
                downloaded += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"Download Summary")
    print(f"{'='*60}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (already existed): {skipped}")
    print(f"Failed: {failed}")
    print(f"Total in output dir: {len(os.listdir(args.output_dir))}")
    print(f"Output: {args.output_dir}")


if __name__ == "__main__":
    main()
