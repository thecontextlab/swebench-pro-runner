#!/usr/bin/env python3
"""Package the 115-task batch into the ETL-compatible archive format.

Produces (under reports/bito_115_opus46_archive/):
  audit_report.csv
  audit_report.json
  parse_verification_logs.py   (copy so the archive is self-contained)
  claude-opus-4-6-<repo>-<base_commit_sha>/
      agent.log
      changes.patch
      pre_verification.log
      result.json
      verification.log
  ... (×115)

Matches the folder convention + file set of
/Users/manoj/sources/research/swe-bench-pro/100-tasks-codex5-2-vs-opus4-6/
so the client's ETL can consume it directly.

Usage:
    python3 scripts/package_115_archive.py

Inputs:
    /tmp/fire_115_runs.txt — 115 GH Actions run IDs (one per line)
    (run IDs are captured by scripts/fire_115_opus46.sh)

Requires: artifacts already downloaded to /tmp/bito-115/<run_id>/
(if not, they will be downloaded here).
"""
import argparse, csv, glob, json, os, re, shutil, subprocess, sys, tarfile, yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path("/Users/manoj/sources/swebench-pro-runner")
# All configurable via env vars so the same script packages different models/batches.
RUN_IDS_PATH = Path(os.environ.get("RUN_IDS_PATH", "/tmp/fire_115_runs.txt"))
DOWNLOAD_BASE = Path(os.environ.get("DOWNLOAD_BASE", "/tmp/bito-115"))
ARCHIVE_DIR = Path(os.environ.get("ARCHIVE_DIR", str(REPO_ROOT / "reports" / "bito_115_opus46_archive")))
TARBALL = Path(os.environ.get("TARBALL", str(REPO_ROOT / "reports" / "bito_115_opus46.tar.gz")))
MODEL_PREFIX = os.environ.get("MODEL_PREFIX", "claude-opus-4-6")

# Files the ETL expects in each task folder (reference format).
ETL_FILES = [
    "agent.log",
    "changes.patch",
    "pre_verification.log",
    "result.json",
    "verification.log",
]


def download_if_needed(run_id: str) -> str:
    """Ensure /tmp/bito-115/<run_id>/swebench-bito-*/ exists."""
    parent = DOWNLOAD_BASE / run_id
    if list(parent.glob("swebench-bito-*/")):
        return run_id
    parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["gh", "run", "download", run_id, "--dir", str(parent)],
        check=False, capture_output=True,
    )
    return run_id


def get_etl_dir(run_id: str) -> Path | None:
    """Return the ETL artifact dir path (not debug)."""
    parent = DOWNLOAD_BASE / run_id
    for d in parent.glob("swebench-bito-*/"):
        if "debug" not in d.name:
            return d
    return None


def extract_repo_and_base_sha(task_id: str, display_title: str = "") -> tuple[str, str]:
    """From a task id like 'internetarchive__openlibrary-03095f2680f7...-v8717e189...'
    return (repo, base_commit_sha).

    If the task_id is parseable, we use it. Otherwise fall back to parsing the GH
    run's displayTitle (which contains '| <repo> | <task> | ...').
    """
    if not task_id and display_title:
        parts = display_title.split(" | ")
        if len(parts) >= 3:
            task_id = parts[2]
    if not task_id:
        return "", ""
    # Split on double-underscore to get owner__repo
    if "__" in task_id:
        owner_repo, rest = task_id.split("__", 1)
        # The repo name is the part after __, before the first 40-char hex
        m = re.match(r"^(.*?)-([0-9a-f]{40})(?:-v[0-9a-f]{40})?$", rest)
        if m:
            repo = m.group(1)
            base_sha = m.group(2)
            return repo, base_sha
    # Fallback: assume task_id itself starts with "<repo>-<sha>"
    m = re.match(r"^([A-Za-z0-9._-]+?)-([0-9a-f]{40})", task_id)
    if m:
        return m.group(1), m.group(2)
    return "", ""


def run_display_title(run_id: str) -> str:
    try:
        return json.loads(subprocess.check_output(
            ["gh", "run", "view", run_id, "--json", "displayTitle"],
            text=True, stderr=subprocess.DEVNULL,
        )).get("displayTitle", "")
    except Exception:
        return ""


def copy_task(run_id: str) -> dict:
    """Copy one run's ETL artifact into the archive folder named
    claude-opus-4-6-<repo>-<base_sha>. Returns a dict of what happened."""
    result = {"run_id": run_id, "status": "error", "reason": ""}
    etl = get_etl_dir(run_id)
    if etl is None:
        result["reason"] = "no-etl-artifact"
        return result
    title = run_display_title(run_id)
    parts = title.split(" | ")
    task_id = parts[2] if len(parts) >= 3 else ""
    repo, base_sha = extract_repo_and_base_sha(task_id, title)
    if not (repo and base_sha):
        result["reason"] = f"cannot-parse-task-id: '{task_id}'"
        return result
    dst = ARCHIVE_DIR / f"{MODEL_PREFIX}-{repo}-{base_sha}"
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for fname in ETL_FILES:
        src = etl / fname
        if src.exists():
            shutil.copy2(src, dst / fname)
            copied.append(fname)
    result.update({
        "status": "ok" if len(copied) >= 4 else "partial",
        "repo": repo,
        "base_sha": base_sha,
        "task_id": task_id,
        "copied": copied,
        "folder": dst.name,
    })
    return result


def build_archive():
    run_ids = [x.strip() for x in RUN_IDS_PATH.read_text().splitlines() if x.strip()]
    print(f"[pkg] {len(run_ids)} runs", file=sys.stderr)

    if ARCHIVE_DIR.exists():
        print(f"[pkg] cleaning existing {ARCHIVE_DIR}", file=sys.stderr)
        shutil.rmtree(ARCHIVE_DIR)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Parallel downloads
    print(f"[pkg] downloading artifacts (8 parallel)...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, _ in enumerate(as_completed([pool.submit(download_if_needed, r) for r in run_ids]), 1):
            if i % 20 == 0:
                print(f"[pkg] downloaded {i}/{len(run_ids)}", file=sys.stderr)

    # Copy into archive folders
    copy_results = []
    for i, rid in enumerate(run_ids, 1):
        res = copy_task(rid)
        copy_results.append(res)
        if i % 20 == 0:
            ok = sum(1 for r in copy_results if r["status"] == "ok")
            print(f"[pkg] copied {i}/{len(run_ids)}  (ok={ok})", file=sys.stderr)

    # Copy the verification-log parser so the archive is self-contained
    parser_src = REPO_ROOT / "scripts" / "parse_verification_logs.py"
    if parser_src.exists():
        shutil.copy2(parser_src, ARCHIVE_DIR / "parse_verification_logs.py")

    # Run the parser to classify each task by its actual log output
    print(f"[pkg] running parse_verification_logs on archive...", file=sys.stderr)
    env = os.environ.copy()
    env["BASE_DIR"] = str(ARCHIVE_DIR)
    subprocess.run(
        ["python3", str(ARCHIVE_DIR / "parse_verification_logs.py")],
        cwd=ARCHIVE_DIR, env=env, check=False,
    )

    # Build audit_report.csv + audit_report.json reconciling rj_resolved (from
    # result.json) with true_resolved (from the classifier).
    write_audit_reports(copy_results)

    # Tarball
    print(f"[pkg] creating {TARBALL} ...", file=sys.stderr)
    if TARBALL.exists():
        TARBALL.unlink()
    with tarfile.open(TARBALL, "w:gz") as tf:
        tf.add(ARCHIVE_DIR, arcname=ARCHIVE_DIR.name)
    print(f"[pkg] tarball size: {TARBALL.stat().st_size / 1024 / 1024:.1f} MB", file=sys.stderr)


def classify_from_parser_md(md_path: Path) -> dict[str, str]:
    """Pull per-task classification out of evaluation_audit_report_logbased.md.

    The md output of parse_verification_logs.py is a results TABLE where
    each row looks like:

      | N | repo | repo-shorthash | framework | ...counts... | CLASSIFICATION |

    We return a lookup keyed by "<repo>-<short8hex>" (e.g. "openlibrary-08ac40d0")
    -> classification string. Callers derive the same key from each folder name.
    """
    classifications: dict[str, str] = {}
    if not md_path.exists():
        return classifications
    # Match a data row (skip the header row that contains "Repo" / "Framework")
    # Expect last column before the final | to be the classification.
    row_re = re.compile(
        r"^\|\s*\d+\s*\|\s*([A-Za-z0-9._-]+)\s*\|\s*([A-Za-z0-9._-]+-[0-9a-f]{6,})\s*\|"
        r".*?\|\s*([A-Z_]+)\s*\|\s*$",
        re.M,
    )
    for m in row_re.finditer(md_path.read_text(errors="replace")):
        _repo, task_short, classification = m.group(1), m.group(2), m.group(3)
        classifications[task_short] = classification
    return classifications


def folder_to_task_short(folder_name: str) -> str | None:
    """<MODEL_PREFIX>-openlibrary-08ac40d050a64e...  ->  openlibrary-08ac40d0
    Matches the md's short-id format (<repo>-<first 8 hex chars of sha>)."""
    pat = re.escape(MODEL_PREFIX) + r"-(.+?)-([0-9a-f]{40})$"
    m = re.match(pat, folder_name)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)[:8]}"


def write_audit_reports(copy_results):
    """Emit audit_report.csv + audit_report.json matching reference schema."""
    # Load classifications from the md that parse_verification_logs.py produced.
    md_path = ARCHIVE_DIR / "evaluation_audit_report_logbased.md"
    classifications = classify_from_parser_md(md_path)

    rows = []
    for r in copy_results:
        if r["status"] != "ok":
            continue
        folder = ARCHIVE_DIR / r["folder"]
        result_json = folder / "result.json"
        try:
            d = json.loads(result_json.read_text(errors="replace"))
        except Exception:
            d = {}
        rj_resolved = bool(d.get("resolved", False))
        tests = d.get("tests") or {}
        # The classifier md uses the short task key <repo>-<sha[:8]>, not the full folder.
        key = folder_to_task_short(r["folder"])
        true_cls = classifications.get(key or "", "")
        # STRICT resolve rule. TESTS_ALREADY_PASSING means the F2P tests passed pre-agent
        # (the task's bug didn't reproduce) so it is a broken task, not a solved one.
        # PARTIALLY_RESOLVED means some failures remain — not a full solve either.
        true_resolved = (true_cls == "RESOLVED")
        # Reconcile
        if rj_resolved and true_resolved:
            category = "TRUE-POSITIVE"
        elif (not rj_resolved) and (not true_resolved):
            category = "TRUE-NEGATIVE"
        elif rj_resolved and (not true_resolved):
            category = "FALSE-POSITIVE"
        else:
            category = "FALSE-NEGATIVE"
        rows.append({
            "repo": r["repo"],
            "task_id": r["task_id"],
            "rj_resolved": str(rj_resolved),
            "true_resolved": str(true_resolved),
            "category": category,
            "subcategory": "",
            "ftp_count": tests.get("total", 0),
            "ftp_passed": tests.get("passed", 0),
            "ftp_failed": tests.get("failed", 0),
            "ftp_not_found": 0,
            "ftp_not_exist": 0,
            "early_stop": "False",
            "crash_type": "",
            "detail": true_cls or "",
        })

    csv_path = ARCHIVE_DIR / "audit_report.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [
            "repo","task_id","rj_resolved","true_resolved","category","subcategory",
            "ftp_count","ftp_passed","ftp_failed","ftp_not_found","ftp_not_exist",
            "early_stop","crash_type","detail",
        ])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    summary = {
        "true_positive": sum(1 for r in rows if r["category"] == "TRUE-POSITIVE"),
        "true_negative": sum(1 for r in rows if r["category"] == "TRUE-NEGATIVE"),
        "false_positive": sum(1 for r in rows if r["category"] == "FALSE-POSITIVE"),
        "false_negative": sum(1 for r in rows if r["category"] == "FALSE-NEGATIVE"),
        "rj_resolved": sum(1 for r in rows if r["rj_resolved"] == "True"),
        "true_resolved": sum(1 for r in rows if r["true_resolved"] == "True"),
    }
    errors = [r for r in copy_results if r["status"] != "ok"]
    json_payload = {
        "label": "Bito 3-stage · Claude Opus 4.6 · 115 tasks (hardened pipeline)",
        "total": len(rows),
        "errors": errors,
        "results": rows,
        "summary": summary,
    }
    json_path = ARCHIVE_DIR / "audit_report.json"
    json_path.write_text(json.dumps(json_payload, indent=2))

    print(f"[pkg] audit_report.csv : {len(rows)} rows", file=sys.stderr)
    print(f"[pkg] summary: {summary}", file=sys.stderr)
    if errors:
        print(f"[pkg] {len(errors)} rows excluded from audit_report (errors)", file=sys.stderr)


if __name__ == "__main__":
    build_archive()
