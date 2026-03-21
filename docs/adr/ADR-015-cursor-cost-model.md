# ADR-015: Cursor Cost Model — Subscription-Based Pricing

## Status

Proposed

## Context

The SWE-bench Pro Runner tracks per-task costs in `result.json` (`total_cost_usd`) and uses cost estimates in orchestration scripts (`launch_tasks.py`) for budget confirmation before batch runs. Claude, Codex, and Gemini all use per-token billing with known pricing tables, enabling precise cost tracking.

Cursor uses a **subscription-based pricing model** — API usage is billed against a monthly subscription tier, not per-token. The Cursor CLI's JSON output may or may not include token counts for the underlying model calls.

This creates a challenge for cost comparisons across agents: reporting `$0.00` for Cursor alongside `$0.30` for Claude Sonnet on the same task makes cross-agent cost analysis misleading.

## Decision

Take a two-layer approach:

1. **If Cursor's JSON output includes token counts:** Calculate estimated cost using the underlying model's pricing table (already defined in `extract_metrics.py` for Claude, GPT, and Gemini models). Add a `cost_model: "estimated_from_tokens"` field to `result.json`.

2. **If no token data is available (default):** Report `total_cost_usd: 0.0` and add `cost_model: "subscription"` to `result.json`. In `launch_tasks.py`, use a fixed estimate of `$0.00` with a log warning.

3. **In reports:** `generate_report.py` adds a footnote when Cursor results are present: "Cursor costs reflect subscription pricing; per-task cost is not directly comparable to per-token-billed agents."

## Consequences

- **Positive:** Honest reporting — no fabricated cost numbers. The `cost_model` field enables downstream tools to handle Cursor results differently.
- **Negative:** Direct cost comparisons between Cursor and other agents are not meaningful. Resolution rate and quality comparisons remain valid.
- **Mitigation:** The research analysis can focus on resolution rate, duration, and quality metrics for Cursor vs. other agents, using cost as a secondary dimension with appropriate caveats.
