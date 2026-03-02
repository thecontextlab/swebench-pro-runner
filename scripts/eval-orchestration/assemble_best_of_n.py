#!/usr/bin/env python3
"""Assemble best-of-N dataset from multiple evaluation runs.

Replaces: assemble_codex52_bestof2_report.py, assemble_codex52_bestof3_report.py.

Takes N source directories with labels, selects the best result per task using
priority rules (resolved > no-rate-limit > no-turn-failed > latest-source),
copies best artifacts to output directory, and generates selection metadata CSV.
"""

import argparse
import csv
import json
import os
import shutil
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _utils import (get_repo_from_folder, get_hash_part, load_result,
                     extract_metrics, scan_agent_log, index_artifact_dir)


def pick_best(candidates, source_priority):
    """Pick the best run from a list of (source_name, path, result, log_flags) tuples.

    Rules:
      1. resolved=True wins
      2. Among ties, prefer no rate limiting
      3. Among ties, prefer no turn.failed
      4. Among ties, prefer latest source (highest priority number)
    """
    def sort_key(c):
        source, path, result, flags = c
        resolved = result.get("resolved", False) if result else False
        return (
            1 if resolved else 0,
            0 if flags["rate_limited"] else 1,
            0 if flags["turn_failed"] else 1,
            source_priority.get(source, 0),
        )

    candidates.sort(key=sort_key, reverse=True)
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(
        description="Assemble best-of-N dataset from multiple evaluation runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Best-of-two from original and rerun
  python3 assemble_best_of_n.py \\
    --sources "original=/path/to/original,rerun=/path/to/rerun" \\
    --output-dir ./eval-bestof2

  # Best-of-three with priority ordering
  python3 assemble_best_of_n.py \\
    --sources "original=/path1,rerun=/path2,tier5=/path3" \\
    --output-dir ./eval-bestof3 \\
    --exclude-tasks f8e7fea0becae25ae20606f1422068137189fe9e

Source format: comma-separated "label=path" pairs.
Sources listed later have higher priority when tied.
""",
    )
    parser.add_argument("--sources", required=True,
                        help="Comma-separated label=path pairs (e.g. 'original=/path1,rerun=/path2')")
    parser.add_argument("--output-dir", required=True, help="Directory to copy best artifacts into")
    parser.add_argument("--exclude-tasks", nargs="*", default=[],
                        help="Hash parts of broken/excluded tasks")
    parser.add_argument("--no-copy", action="store_true",
                        help="Skip copying artifacts (only generate CSV)")
    args = parser.parse_args()

    # Parse sources
    sources = []
    for item in args.sources.split(","):
        item = item.strip()
        if "=" not in item:
            print(f"Error: source must be label=path format: {item}", file=sys.stderr)
            sys.exit(1)
        label, path = item.split("=", 1)
        sources.append((label.strip(), path.strip()))

    # Build source priority (later = higher priority)
    source_priority = {label: i + 1 for i, (label, _) in enumerate(sources)}

    print(f"Sources ({len(sources)}):")
    for label, path in sources:
        exists = os.path.isdir(path)
        print(f"  {label}: {path} {'[OK]' if exists else '[MISSING]'}")

    broken_set = set(args.exclude_tasks)
    if broken_set:
        print(f"Excluding {len(broken_set)} broken tasks")

    # Index all source directories
    indexed_sources = []
    for label, path in sources:
        index = index_artifact_dir(path)
        indexed_sources.append((label, index))
        print(f"  {label}: {len(index)} task folders")

    # Collect all unique task hash parts
    all_tasks = set()
    for _, index in indexed_sources:
        all_tasks.update(index.keys())
    all_tasks = sorted(all_tasks)
    print(f"\nTotal unique tasks: {len(all_tasks)}")

    os.makedirs(args.output_dir, exist_ok=True)

    # Best-of-N selection
    selections = []
    source_counts = defaultdict(int)

    for hp in all_tasks:
        if hp in broken_set:
            continue

        candidates = []
        for label, index in indexed_sources:
            path = index.get(hp)
            if path:
                result = load_result(path)
                agent_log = os.path.join(path, "agent.log")
                flags = scan_agent_log(agent_log)
                candidates.append((label, path, result, flags))

        if not candidates:
            continue

        best_source, best_path, best_result, best_flags = pick_best(candidates, source_priority)

        # Build reason string
        resolved_map = {c[0]: c[2].get("resolved", False) if c[2] else False for c in candidates}
        if len(candidates) == 1:
            reason = f"only-{best_source}"
        elif best_result and best_result.get("resolved", False):
            multi_resolved = sum(1 for v in resolved_map.values() if v) > 1
            reason = f"multi-resolved-prefer-{best_source}" if multi_resolved else f"{best_source}-resolved"
        else:
            reason = f"neither-prefer-{best_source}"

        folder_name = os.path.basename(best_path)
        repo = get_repo_from_folder(folder_name)
        source_counts[best_source] += 1

        selections.append({
            "hash_part": hp,
            "repo": repo,
            "folder_name": folder_name,
            "chosen_path": best_path,
            "choice": best_source,
            "reason": reason,
            "result": best_result,
            "rate_limited": best_flags["rate_limited"],
            "turn_failed": best_flags["turn_failed"],
            "candidates": len(candidates),
            "resolved_by_source": resolved_map,
        })

    # Copy best artifacts
    if not args.no_copy:
        print(f"\nCopying best artifacts to {args.output_dir}...")
        for sel in selections:
            src = sel["chosen_path"]
            dst = os.path.join(args.output_dir, sel["folder_name"])
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        print(f"Copied {len(selections)} task folders")

    # Generate CSV with selection metadata and metrics
    csv_path = os.path.join(args.output_dir, "selection_metadata.csv")
    csv_rows = []
    for sel in selections:
        m = extract_metrics(sel["result"])
        csv_rows.append({
            "repo": sel["repo"],
            "task_id": sel["hash_part"],
            "resolved": str(m["resolved"]).lower(),
            "source": sel["choice"],
            "reason": sel["reason"],
            "candidates": sel["candidates"],
            "rate_limited": str(sel["rate_limited"]).lower(),
            "turn_failed": str(sel["turn_failed"]).lower(),
            "duration_seconds": m["duration_seconds"],
            "duration_api_seconds": m["duration_api_seconds"],
            "total_cost_usd": m["total_cost_usd"],
            "tokens_input": m["tokens_input"],
            "tokens_output": m["tokens_output"],
            "tokens_cache_read": m["tokens_cache_read"],
            "total_tool_calls": m["total_tool_calls"],
            "num_turns": m["num_turns"],
        })

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "repo", "task_id", "resolved", "source", "reason", "candidates",
            "rate_limited", "turn_failed",
            "duration_seconds", "duration_api_seconds", "total_cost_usd",
            "tokens_input", "tokens_output", "tokens_cache_read",
            "total_tool_calls", "num_turns",
        ])
        writer.writeheader()
        for row in sorted(csv_rows, key=lambda x: (x["repo"], x["task_id"])):
            writer.writerow(row)
    print(f"Selection metadata CSV: {csv_path}")

    # Summary
    total = len(selections)
    resolved = sum(1 for s in selections if s["result"] and s["result"].get("resolved", False))

    print(f"\n{'='*60}")
    print(f"Assembly Summary")
    print(f"{'='*60}")
    print(f"Total tasks: {total}")
    print(f"Resolved: {resolved}/{total} ({resolved/total*100:.1f}%)")
    print(f"\nSource selection:")
    for label, _ in sources:
        count = source_counts.get(label, 0)
        print(f"  {label}: {count}")
    print(f"Output: {args.output_dir}")


if __name__ == "__main__":
    main()
