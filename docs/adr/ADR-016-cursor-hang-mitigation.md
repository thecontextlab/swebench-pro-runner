# ADR-016: Cursor CLI Hang Mitigation — Idle Timeout Watchdog

## Status

Proposed

## Context

The Cursor CLI (beta) has a known issue where the process may hang indefinitely after completing its response in `--print` mode. The process produces output normally during execution but then fails to exit, consuming the full GHA step timeout (default 45 minutes) without doing useful work.

This is particularly dangerous in our evaluation pipeline:
- A hung process burns CI compute credits for up to 45 minutes per task.
- At scale (100 tasks), a systematic hang could waste hours of CI time.
- The existing GHA `timeout-minutes` is a blunt instrument — it kills the entire step, potentially losing partial results.

The other three CLIs (Claude, Codex, Gemini) do not have this issue and use simple `subprocess.run()` or `Popen` without watchdogs.

## Decision

Implement a **dual-timeout mechanism** in `run_cursor.py`:

1. **Idle timeout (120 seconds):** A watchdog thread monitors the last timestamp of stdout output from the Cursor process. If no new output arrives for 120 seconds, the watchdog sends SIGTERM, waits 5 seconds, then sends SIGKILL if the process is still alive. This catches the post-completion hang without interrupting legitimate long-running operations (agents produce continuous output while working).

2. **Hard timeout (configurable via env var):** The wrapper respects `CURSOR_HARD_TIMEOUT` env var (default: 2400 seconds / 40 minutes), which is set to 90% of the GHA agent timeout. This ensures the wrapper exits cleanly before the GHA step timeout kills it, preserving partial results in `/results/`.

Both timeouts log distinctive markers (`[wrapper] Cursor idle for >120s, sending SIGTERM`) so the hang is identifiable in `agent.log` and `extract_metrics.py` can flag it.

## Consequences

- **Positive:** Prevents burned CI credits from hung processes. Preserves partial results (agent.log, changes.patch) even when the process hangs. Distinctive log markers enable automated detection in audit scripts.
- **Negative:** May prematurely kill a legitimately slow Cursor process that produces no output for >120s (unlikely — agents produce continuous tool-use output). The 120s threshold is tunable via `CURSOR_IDLE_TIMEOUT` env var.
- **Future:** If Cursor CLI fixes the hang issue, the watchdog becomes a no-op (process exits before idle timeout). No code changes needed — it's purely protective.
