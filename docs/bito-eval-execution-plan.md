# Bito 3-Stage Pipeline Evaluation — Execution Plan

## Goal

Run 115 SWE-bench Pro tasks through a 3-stage Bito pipeline (scope-to-plan → plan-to-agent-spec → agent-spec-executor) against two Claude models: Opus 4.6 and Opus 4.7 (effort `xhigh`). MCP enabled via BitoAIArchitect.

## Scope

- **Repos covered** (4): openlibrary (33), teleport (40), tutanota (9), webclients (33). 115 tasks total.
- **Validation repo** (1): vuls (sanity check, not in the 115).
- **Models**: `claude-opus-4-6`, `claude-opus-4-7`.
- **Effort**: `xhigh` (new `--effort` CLI flag in Claude Code, session-scoped).
- **MCP endpoint**: `https://mcp.bito.ai/982268/mcp`, bearer token stored as GHA secret `MCP_TOKEN`.
- **API key**: client-provided Anthropic key in GHA secret `ANTHROPIC_API_KEY`.

## Inputs (already in repo root)

- `SKILLS.zip` — 12 Bito skills (`bito-scope-to-plan`, `bito-plan-to-agent-spec`, `bito-agent-spec-executor`, plus 9 others).
- `BitoAIArchitectGuidelines.md` — written into `/testbed/CLAUDE.md` at runtime so Claude auto-loads it.
- `bito_pipeline_three_stage_prompts.md` — prompt templates for the three stages.
- `swe_pro_eval_tasks_bito_skills copy.csv` — 115-task list (short hashes; needs resolution to full YAML filenames).

## Workflow shape

**New workflow**: `.github/workflows/swebench-eval-bito.yml` — separate from existing `swebench-eval.yml`. Hardcoded: MCP on, 3-stage pipeline. Repo dropdown: openlibrary / teleport / tutanota / webclients / vuls. Model dropdown: opus-4-6 / opus-4-7. Effort input defaults to `xhigh`.

### Step order
1. Checkout eval-runner
2. Load task YAML + resolve Docker image
3. Pull prebaked image
4. **Install skills** — bind-mount `SKILLS/` (unzipped) to `/root/.claude/skills/` in container
5. **Verify skills** — assert all 12 skill directories present; fail fast if not
6. Clone repo + run `before_repo_set_cmd` + `setup.sh`
7. Pre-verify F2P fail + P2P pass (baseline)
8. Write `BitoAIArchitectGuidelines.md` → `/testbed/CLAUDE.md`
9. **Stage 1** (`run_claude_stage1.py`) — scope-to-plan; verify `pipeline_artifacts/implementation-plan.md` exists
10. **Stage 2** (`run_claude_stage2.py`) — plan-to-agent-spec; verify manifest + at least one spec file
11. **Stage 3** (`run_claude_stage3.py`) — single Claude instance runs executor skill sequentially per workstream from the manifest
12. `git diff` → `changes.patch`
13. Post-verify F2P + P2P (regression check)
14. Archive `pipeline_artifacts/` + per-stage logs under `/results/`
15. `extract_metrics.py` aggregates tokens/cost across three stage logs

### Prompt injection

Each stage wrapper reads its prompt template from `bito_pipeline_three_stage_prompts.md` (mounted read-only into the container) and substitutes `{INSERT_PROBLEM_STATEMENT_HERE}` with `/instruction.txt`. Stage 3 prompt gets an added line: *"Use the BitoAIArchitect MCP server heavily during execution to look up patterns, callers, and ripple risk before making changes."*

BitoAIArchitect usage is reinforced three ways:
1. `/testbed/CLAUDE.md` auto-loaded on Claude startup (opens with "CALL FIRST FOR ALL TASKS")
2. Each stage prompt explicitly says "Use the BitoAIArchitect MCP server heavily"
3. Skills themselves invoke it via their SKILL.md instructions

## Phases

### Phase 1 — Scaffolding
1. `scripts/eval-orchestration/csv_to_task_file.py` — CSV short-hash → full YAML filename resolver. Outputs `bito_115.txt` and `bito_sample.txt` (6 tasks).
2. Patch `bito_pipeline_three_stage_prompts.md` Stage 3 with the BitoAIArchitect line.
3. `datasets/common/run_claude_stage{1,2,3}.py` — shared stage wrappers (one copy, not per-repo).
4. `.github/workflows/swebench-eval-bito.yml` — new workflow.
5. Dockerfile changes: `COPY SKILLS/` and `COPY BitoAIArchitectGuidelines.md` baked in. Or bind-mount from workspace for lower-cost iteration — TBD based on image rebuild cost.

### Phase 2 — GHA secrets
6. User adds `ANTHROPIC_API_KEY` and confirms `MCP_TOKEN=d2b8c48b-da51-4516-a28e-b86f2950fb6b` is set.
7. Per-repo `config.yaml` (4 repos) gets `mcp.url: https://mcp.bito.ai/982268/mcp`.

### Phase 3 — Sample run (6 tasks)
| # | Repo | Task (full ID) |
|---|------|-----|
| 1 | openlibrary | `internetarchive__openlibrary-00bec1e7c8f3272c469a58e1377df03f955ed478-v13642507b4fc1f8d234172bf8129942da2c2ca26` |
| 2 | openlibrary | `internetarchive__openlibrary-03095f2680f7516fca35a58e665bf2a41f006273-v8717e18970bcdc4e0d2cea3b1527752b21e74866` |
| 3 | teleport | `gravitational__teleport-005dcb16bacc6a5d5890c4cd302ccfd4298e275d-vee9b09fb20c43af7e520f57e9239bbcf46b7113d` |
| 4 | tutanota | `tutao__tutanota-09c2776c0fce3db5c6e18da92b5a45dce9f013aa-vbc0d9ba8f0071fbe982809910959a6ff8884dbbf` |
| 5 | webclients | `protonmail__webclients-01b519cd49e6a24d9a05d2eb97f54e420740072e` |
| 6 | vuls (validation) | `future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c` |

Dispatch manually one at a time; review artifacts (`pipeline_artifacts/`, `stage{1,2,3}.log`, `result.json`). Iterate on wrappers/prompts as needed.

### Phase 4 — Full run
8. Generate `bito_115.txt` from CSV.
9. Dry-run launch for both models:
   ```
   launch_tasks.py --task-file bito_115.txt --agent claude --model claude-opus-4-6 --mcp true --delay 30 --dry-run
   launch_tasks.py --task-file bito_115.txt --agent claude --model claude-opus-4-7 --mcp true --delay 30 --dry-run
   ```
   (Launcher needs `--effort` passthrough; add if missing.)
10. Confirm API key budget with client, then remove `--dry-run`.
11. Monitor with `monitor_runs.py`; download + report with existing orchestration scripts.

## Cost estimate

115 tasks × 3 Claude invocations × ~$3 Opus per invocation ≈ **~$1,000/model**, **~$2,000 total** (rough; xhigh effort may increase this).

## Open items tracked outside this doc

- Whether Docker images bake skills in or bind-mount (affects image rebuild frequency).
- Whether `extract_metrics.py` per-repo needs updates for three-log aggregation (likely yes).
- `launch_tasks.py` may need an `--effort` passthrough flag.
