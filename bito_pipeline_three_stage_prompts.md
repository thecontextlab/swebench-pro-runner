# Bito Pipeline — Three-Stage User Prompts (v2)

Each prompt below is injected into a separate Claude Code instance. The skills themselves define the output file conventions — these prompts just ensure each stage knows where to find its inputs and writes outputs to a shared `pipeline_artifacts/` directory in the repo root.

---

## STAGE 1 — Scope to Plan (`/bito-scope-to-plan`)

```
You are running Stage 1 of a 3-stage Bito pipeline for solving a SWE-Bench Pro task. Your job is to produce a technical implementation plan using the `/bito-scope-to-plan` skill.

### Context
This is an automated benchmark run. Three separate Claude Code instances handle the three stages. You are Stage 1. Your output — the implementation plan document — will be consumed by Stage 2 (running `/bito-plan-to-agent-spec`) in a separate instance. Save your final plan to `pipeline_artifacts/` in the repo working directory so the next stage can find it.

### What you must do

1. Create `pipeline_artifacts/` in the current repo working directory if it doesn't exist.

2. Invoke `/bito-scope-to-plan` with the problem statement below as the **approved** unit of work.
   - The problem statement IS the approved scope. Treat it as pre-approved — skip any scope-clarification step.
   - Use the BitoAIArchitect MCP server heavily during planning to understand codebase structure, dependencies, and relevant code paths.
   - **Auto-approve all checkpoints.** The skill has three checkpoints (context summary confirmation, approach selection, plan review). At each one, auto-approve — select the most appropriate approach and confirm with "approved" / "continue". Do not stall waiting for user input.

3. The skill will produce a final plan document per its output template (references/output-templates.md). Save that plan to `pipeline_artifacts/implementation-plan.md`.

### Hard rules
- **No user prompts.** Do not ask the user anything. Run fully autonomously.
- **Do NOT modify any test file.**
- **Do NOT consult any gold patch.** Work only from the problem statement.
- Focus on the minimal change needed to fix the issue described.
- At every skill checkpoint, auto-approve and continue immediately.

### Problem statement
<PROBLEM_STATEMENT>
{INSERT_PROBLEM_STATEMENT_HERE}
</PROBLEM_STATEMENT>

When the plan is saved to `pipeline_artifacts/implementation-plan.md`, stop. Do not proceed to the next stage.
```

---

## STAGE 2 — Plan to Agent Spec (`/bito-plan-to-agent-spec`)

```
You are running Stage 2 of a 3-stage Bito pipeline for solving a SWE-Bench Pro task. Stage 1 (a different Claude Code instance) already produced a technical implementation plan. Your job is to transform that plan into workstream agent specs using the `/bito-plan-to-agent-spec` skill.

### Context
This is an automated benchmark run. You are Stage 2. Your input is the plan from Stage 1 on disk. Your outputs — the agent spec files and execution manifest — will be consumed by Stage 3 (running `/bito-agent-spec-executor`) in a separate instance.

### What you must do

1. Read the plan from `pipeline_artifacts/implementation-plan.md`.

2. Invoke `/bito-plan-to-agent-spec` on that plan.
   - Use the BitoAIArchitect MCP server heavily to enrich specs with codebase context — directory structure, pattern exemplars, build/test commands, coding standards, ripple risks.
   - **Auto-approve all checkpoints.** The skill has two checkpoints (workstream graph confirmation, spec review). At each one, auto-approve — confirm with "approved" / "looks good" / "continue". Do not stall waiting for user input.

3. The skill will produce:
   - One agent spec file per workstream, named per its convention: `{ticket-id}-ws{N}-{slug}.agent-spec.md`
   - An execution manifest: `{ticket-id}-execution-manifest.md`

   Since this is a SWE-Bench task with no ticket ID, use `swebench` as the ticket-id prefix (e.g., `swebench-ws1-data-model.agent-spec.md`, `swebench-execution-manifest.md`).

   Save all output files into `pipeline_artifacts/`.

### Hard rules
- **No user prompts.** Do not ask the user anything. Run fully autonomously.
- **Do NOT modify any test file.**
- **Do NOT modify any source code.** Your job is spec production only.
- **Do NOT consult any gold patch.** Work only from the plan.
- At every skill checkpoint, auto-approve and continue immediately.

When all agent spec files and the execution manifest are saved to `pipeline_artifacts/`, stop. Do not proceed to the next stage.
```

---

## STAGE 3 — Agent Spec Executor (`/bito-agent-spec-executor`)

```
You are running Stage 3 of a 3-stage Bito pipeline for solving a SWE-Bench Pro task. Stages 1 and 2 (different Claude Code instances) already produced an implementation plan and workstream agent specs. Your job is to execute each agent spec using the `/bito-agent-spec-executor` skill, making actual code changes in the repo.

### Context
This is an automated benchmark run. You are Stage 3 — the executor. The skill requires TWO inputs per invocation: (1) the original implementation plan and (2) one workstream agent-spec file. Both are in `pipeline_artifacts/`.

### What you must do

1. Read `pipeline_artifacts/swebench-execution-manifest.md` to get the list of workstream spec files, their execution wave order, and the total workstream count.

2. Read the implementation plan from `pipeline_artifacts/implementation-plan.md` — this provides architectural context needed by the executor.

3. For each agent spec file listed in the manifest, in wave order (sequential within waves for this benchmark):
   a. Invoke `/bito-agent-spec-executor` with both the implementation plan and the current workstream spec file as inputs.
   b. The executor **must make the actual code changes** in the repo — it must not stop at planning.
   c. Use the BitoAIArchitect MCP server heavily during execution to look up patterns, callers, and ripple risk before making changes.
   d. If the skill hits any checkpoint or confirmation prompt, auto-approve with "approved" / "continue" / "yes" and keep going.
   e. The executor will run its own verification gates and two-stage review (spec compliance + code quality) per the skill definition. Let it complete fully.

4. If the manifest lists N workstreams, invoke the executor N times, once per spec, sequentially.

### Hard rules
- **No user prompts.** Do not ask the user anything. Run fully autonomously.
- **Do NOT modify any test file.**
- **Do NOT consult any gold patch.** Work only from the workstream specs and implementation plan.
- Make the **minimal change** needed to fix the issue. Do not refactor unrelated code.
- At every skill checkpoint or confirmation prompt, auto-approve and continue.
- After all workstreams are executed, note the total workstream count (e.g., "workstreams=3") for downstream recording.
- **Skip branch creation.** The executor skill normally creates a git branch per workstream. For this benchmark, skip branching — make changes directly on the current working tree. All workstreams apply to the same repo state sequentially.

When all workstream specs have been executed and code changes are in the repo, stop. Do not run tests. Do not ask what to do next.
```
