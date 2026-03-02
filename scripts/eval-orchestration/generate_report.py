#!/usr/bin/env python3
"""Generate evaluation report from SWE-bench Pro artifacts.

Replaces: generate_report_20260216.sh, report sections from bestof3 script,
generate_phase2_formatted_csv_complete.py, generate_phase2_baseline_csvs.py.

Auto-detects result.json format (Claude vs Codex), generates markdown report
and CSV, with optional baseline comparison.
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _utils import (get_repo_from_folder, get_hash_part, load_result,
                     extract_metrics, scan_agent_log)


def collect_task_data(artifact_dir, exclude_tasks=None):
    """Collect metrics from all task folders in an artifact directory."""
    exclude = set(exclude_tasks or [])
    tasks = []

    folders = sorted([
        d for d in os.listdir(artifact_dir)
        if os.path.isdir(os.path.join(artifact_dir, d))
        and not d.startswith(".")
    ])

    for folder in folders:
        path = os.path.join(artifact_dir, folder)
        hash_part = get_hash_part(folder)

        is_broken = hash_part in exclude
        result = load_result(path)
        if result is None:
            continue

        m = extract_metrics(result)
        repo = get_repo_from_folder(folder)
        agent_log = os.path.join(path, "agent.log")
        flags = scan_agent_log(agent_log)

        tasks.append({
            "repo": repo,
            "hash_part": hash_part,
            "folder": folder,
            "is_broken": is_broken,
            "metrics": m,
            "rate_limited": flags["rate_limited"],
            "turn_failed": flags["turn_failed"],
        })

    return tasks


def build_repo_metrics(tasks):
    """Aggregate tasks into per-repo and global metrics."""
    repo_data = defaultdict(lambda: {
        "tasks": 0, "resolved": 0, "broken": 0,
        "total_cost": 0, "total_duration": 0, "total_api_duration": 0,
        "total_tool_calls": 0, "total_turns": 0,
        "total_tokens_input": 0, "total_tokens_output": 0, "total_tokens_cache": 0,
        "tool_counts": defaultdict(int),
        "rate_limited": 0, "turn_failed": 0,
    })

    for t in tasks:
        m = t["metrics"]
        repo = t["repo"]
        rd = repo_data[repo]

        rd["tasks"] += 1
        if t["is_broken"]:
            rd["broken"] += 1
        elif m["resolved"]:
            rd["resolved"] += 1
        rd["total_cost"] += m["total_cost_usd"]
        rd["total_duration"] += m["duration_seconds"]
        rd["total_api_duration"] += m["duration_api_seconds"]
        rd["total_tool_calls"] += m["total_tool_calls"]
        rd["total_turns"] += m["num_turns"]
        rd["total_tokens_input"] += m["tokens_input"]
        rd["total_tokens_output"] += m["tokens_output"]
        rd["total_tokens_cache"] += m["tokens_cache_read"]
        if t["rate_limited"]:
            rd["rate_limited"] += 1
        if t["turn_failed"]:
            rd["turn_failed"] += 1

        for tool, count in m["all_tools"].items():
            rd["tool_counts"][tool] += count

    return repo_data


def generate_markdown(tasks, repo_data, compare_tasks=None, compare_label=None):
    """Generate markdown report."""
    report = []
    now = datetime.now().strftime("%a %b %d %H:%M:%S %Z %Y")

    # Detect model from first task
    model = "unknown"
    for t in tasks:
        m = t["metrics"].get("model", "unknown")
        if m != "unknown":
            model = m
            break

    # Global aggregates
    total_tasks = sum(rd["tasks"] for rd in repo_data.values())
    total_broken = sum(rd["broken"] for rd in repo_data.values())
    total_resolved = sum(rd["resolved"] for rd in repo_data.values())
    scoreable = total_tasks - total_broken
    total_cost = sum(rd["total_cost"] for rd in repo_data.values())
    total_duration = sum(rd["total_duration"] for rd in repo_data.values())
    total_tool_calls = sum(rd["total_tool_calls"] for rd in repo_data.values())
    total_turns = sum(rd["total_turns"] for rd in repo_data.values())
    total_input = sum(rd["total_tokens_input"] for rd in repo_data.values())
    total_output = sum(rd["total_tokens_output"] for rd in repo_data.values())
    total_cache = sum(rd["total_tokens_cache"] for rd in repo_data.values())

    report.append(f"# SWE-bench Pro Evaluation Report")
    report.append(f"Generated: {now}")
    report.append("")
    report.append("## Overview")
    report.append(f"- **Model**: {model}")
    report.append(f"- **Repositories**: {len(repo_data)}")
    report.append(f"- **Total tasks**: {total_tasks}")
    if total_broken > 0:
        report.append(f"- **Broken tasks excluded**: {total_broken}")
    report.append("")

    # Per-repo comparison table
    report.append("## Per-Repository Results")
    report.append("")
    report.append("| Repository | Tasks | Resolved | Rate | Avg Cost | Total Cost |")
    report.append("|------------|-------|----------|------|----------|------------|")
    for repo in sorted(repo_data.keys()):
        rd = repo_data[repo]
        t = rd["tasks"]
        b = rd["broken"]
        r = rd["resolved"]
        s = t - b
        rate = f"{r/s*100:.1f}%" if s > 0 else "N/A"
        avg_cost = f"${rd['total_cost']/t:.2f}" if t > 0 else "N/A"
        total_c = f"${rd['total_cost']:.2f}"
        report.append(f"| {repo} | {s} | {r} | {rate} | {avg_cost} | {total_c} |")
    report.append("")

    # Global summary
    report.append("## Global Summary")
    report.append("")
    report.append("| Metric | Value |")
    report.append("|--------|-------|")
    report.append(f"| Total tasks | {total_tasks} |")
    if total_broken > 0:
        report.append(f"| Broken (excluded) | {total_broken} |")
        report.append(f"| Scoreable tasks | {scoreable} |")
    report.append(f"| Total resolved | {total_resolved} |")
    rate_str = f"{total_resolved/scoreable*100:.1f}%" if scoreable > 0 else "N/A"
    report.append(f"| **Overall resolution rate** | **{rate_str}** |")
    report.append(f"| Total cost | ${total_cost:.2f} |")
    report.append(f"| Avg cost per task | ${total_cost/total_tasks:.2f} |" if total_tasks > 0 else "| Avg cost per task | N/A |")
    report.append(f"| Total tokens (input) | {total_input:,} |")
    report.append(f"| Total tokens (output) | {total_output:,} |")
    report.append(f"| Total tokens (cache read) | {total_cache:,} |")
    report.append(f"| Total tool calls | {total_tool_calls:,} |")
    avg_tools = f"{total_tool_calls/total_tasks:.1f}" if total_tasks > 0 else "N/A"
    avg_turns = f"{total_turns/total_tasks:.1f}" if total_tasks > 0 else "N/A"
    report.append(f"| Avg tool calls per task | {avg_tools} |")
    report.append(f"| Avg turns per task | {avg_turns} |")
    report.append("")

    # Tool usage analysis
    global_tools = defaultdict(int)
    for rd in repo_data.values():
        for tool, count in rd["tool_counts"].items():
            global_tools[tool] += count

    if global_tools:
        report.append("## Tool Usage Analysis")
        report.append("")
        report.append("| Tool | Total Calls |")
        report.append("|------|-------------|")
        for tool, count in sorted(global_tools.items(), key=lambda x: -x[1]):
            report.append(f"| {tool} | {count:,} |")
        report.append("")

    # Comparison section
    if compare_tasks and compare_label:
        compare_repo_data = build_repo_metrics(compare_tasks)
        compare_total = sum(rd["tasks"] for rd in compare_repo_data.values())
        compare_broken = sum(rd["broken"] for rd in compare_repo_data.values())
        compare_resolved = sum(rd["resolved"] for rd in compare_repo_data.values())
        compare_scoreable = compare_total - compare_broken
        compare_cost = sum(rd["total_cost"] for rd in compare_repo_data.values())
        compare_tool_calls = sum(rd["total_tool_calls"] for rd in compare_repo_data.values())
        compare_turns = sum(rd["total_turns"] for rd in compare_repo_data.values())

        report.append(f"## Comparison with {compare_label}")
        report.append("")
        report.append(f"| Metric | Current | {compare_label} |")
        report.append(f"|--------|---------|{'—'*len(compare_label)}|")
        cur_rate = f"{total_resolved}/{scoreable} ({total_resolved/scoreable*100:.1f}%)" if scoreable > 0 else "N/A"
        cmp_rate = f"{compare_resolved}/{compare_scoreable} ({compare_resolved/compare_scoreable*100:.1f}%)" if compare_scoreable > 0 else "N/A"
        report.append(f"| Resolution rate | {cur_rate} | {cmp_rate} |")
        report.append(f"| Total cost | ${total_cost:.2f} | ${compare_cost:.2f} |")
        avg_c = f"${total_cost/total_tasks:.2f}" if total_tasks > 0 else "N/A"
        cmp_avg_c = f"${compare_cost/compare_total:.2f}" if compare_total > 0 else "N/A"
        report.append(f"| Avg cost/task | {avg_c} | {cmp_avg_c} |")
        report.append(f"| Total tool calls | {total_tool_calls:,} | {compare_tool_calls:,} |")
        c_avg_turns = f"{compare_turns/compare_total:.1f}" if compare_total > 0 else "N/A"
        report.append(f"| Avg turns/task | {avg_turns} | {c_avg_turns} |")
        report.append("")

        # Per-repo head-to-head
        report.append(f"### Per-Repository Head-to-Head")
        report.append("")
        report.append(f"| Repository | Current | {compare_label} | Delta |")
        report.append(f"|------------|---------|{'—'*len(compare_label)}|-------|")

        all_repos = sorted(set(list(repo_data.keys()) + list(compare_repo_data.keys())))
        for repo in all_repos:
            rd = repo_data.get(repo, {"tasks": 0, "broken": 0, "resolved": 0})
            crd = compare_repo_data.get(repo, {"tasks": 0, "broken": 0, "resolved": 0})

            s1 = rd["tasks"] - rd["broken"]
            r1 = rd["resolved"]
            s2 = crd["tasks"] - crd["broken"]
            r2 = crd["resolved"]

            pct1 = r1 / s1 * 100 if s1 > 0 else 0
            pct2 = r2 / s2 * 100 if s2 > 0 else 0
            delta = pct1 - pct2
            delta_str = f"+{delta:.1f}%" if delta > 0 else f"{delta:.1f}%"

            report.append(f"| {repo} | {r1}/{s1} ({pct1:.0f}%) | {r2}/{s2} ({pct2:.0f}%) | {delta_str} |")
        report.append("")

    report.append("---")
    report.append(f"*Report generated: {now}*")

    return "\n".join(report) + "\n"


def generate_csv_data(tasks):
    """Generate CSV rows from task data."""
    rows = []
    for t in tasks:
        m = t["metrics"]
        rows.append({
            "repo": t["repo"],
            "task_id": t["hash_part"],
            "resolved": str(m["resolved"]).lower(),
            "is_broken": str(t["is_broken"]).lower(),
            "duration_seconds": m["duration_seconds"],
            "duration_api_seconds": m["duration_api_seconds"],
            "total_cost_usd": m["total_cost_usd"],
            "tokens_input": m["tokens_input"],
            "tokens_output": m["tokens_output"],
            "tokens_cache_read": m["tokens_cache_read"],
            "total_tool_calls": m["total_tool_calls"],
            "num_turns": m["num_turns"],
            "rate_limited": str(t["rate_limited"]).lower(),
            "turn_failed": str(t["turn_failed"]).lower(),
            "model": m["model"],
        })
    return sorted(rows, key=lambda x: (x["repo"], x["task_id"]))


def main():
    parser = argparse.ArgumentParser(
        description="Generate evaluation report from SWE-bench Pro artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Generate markdown + CSV report
  python3 generate_report.py --artifact-dir ./eval-codex52-bestof3-20260221

  # Generate with baseline comparison
  python3 generate_report.py --artifact-dir ./eval-codex52-bestof3 \\
    --compare-dir ./eval-opus46-baseline \\
    --compare-label "Claude opus-4-6"

  # Markdown only, exclude broken tasks
  python3 generate_report.py --artifact-dir ./eval-codex52 \\
    --output-format md \\
    --exclude-tasks f8e7fea0becae25ae20606f1422068137189fe9e
""",
    )
    parser.add_argument("--artifact-dir", required=True, help="Directory containing artifact folders")
    parser.add_argument("--output-format", default="md,csv",
                        help="Comma-separated output formats: md, csv (default: md,csv)")
    parser.add_argument("--output-dir", help="Output directory for report files (default: same as artifact-dir)")
    parser.add_argument("--exclude-tasks", nargs="*", default=[],
                        help="Hash parts of broken tasks to exclude from scoring")
    parser.add_argument("--compare-dir", help="Directory of baseline artifacts for comparison")
    parser.add_argument("--compare-label", default="Baseline", help="Label for comparison dataset")
    args = parser.parse_args()

    if not os.path.isdir(args.artifact_dir):
        print(f"Error: {args.artifact_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output_dir or args.artifact_dir
    os.makedirs(output_dir, exist_ok=True)
    formats = [f.strip() for f in args.output_format.split(",")]

    # Collect task data
    tasks = collect_task_data(args.artifact_dir, args.exclude_tasks)
    if not tasks:
        print("No tasks found in artifact directory.")
        return

    print(f"Collected {len(tasks)} tasks from {args.artifact_dir}")

    repo_data = build_repo_metrics(tasks)

    # Comparison data
    compare_tasks = None
    if args.compare_dir and os.path.isdir(args.compare_dir):
        compare_tasks = collect_task_data(args.compare_dir, args.exclude_tasks)
        print(f"Collected {len(compare_tasks)} comparison tasks from {args.compare_dir}")

    # Generate outputs
    if "md" in formats:
        md_content = generate_markdown(tasks, repo_data, compare_tasks, args.compare_label)
        md_path = os.path.join(output_dir, "experiment_report.md")
        with open(md_path, "w") as f:
            f.write(md_content)
        print(f"Markdown report: {md_path}")

    if "csv" in formats:
        csv_rows = generate_csv_data(tasks)
        csv_path = os.path.join(output_dir, "experiment_results.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "repo", "task_id", "resolved", "is_broken",
                "duration_seconds", "duration_api_seconds", "total_cost_usd",
                "tokens_input", "tokens_output", "tokens_cache_read",
                "total_tool_calls", "num_turns", "rate_limited", "turn_failed", "model",
            ])
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"CSV data: {csv_path}")

    # Print summary to stdout
    total = len(tasks)
    broken = sum(1 for t in tasks if t["is_broken"])
    resolved = sum(1 for t in tasks if not t["is_broken"] and t["metrics"]["resolved"])
    scoreable = total - broken
    cost = sum(t["metrics"]["total_cost_usd"] for t in tasks)

    print(f"\n{'='*60}")
    print(f"Report Summary")
    print(f"{'='*60}")
    print(f"Tasks: {total} (broken: {broken}, scoreable: {scoreable})")
    rate = f"{resolved/scoreable*100:.1f}%" if scoreable > 0 else "N/A"
    print(f"Resolved: {resolved}/{scoreable} ({rate})")
    print(f"Total cost: ${cost:.2f}")


if __name__ == "__main__":
    main()
