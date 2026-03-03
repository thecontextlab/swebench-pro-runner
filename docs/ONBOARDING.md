# Onboarding Guide

A structured learning path for new contributors — both human interns and their AI coding agents. Work through the phases in order. Each phase builds on the previous one.

---

## How to Use This Guide

This guide has **5 phases**, designed to take you from zero knowledge to confident contributor. Each phase has:

- **Goal** — what you'll understand by the end
- **Read** — documentation to study
- **Do** — hands-on exercises
- **Checkpoint** — how to verify you're ready to move on

**Time estimate**: A few hours spread over a few days if you're new to everything.

**If you're using an AI coding agent** (Claude Code, Cursor, Copilot, etc.): give it this file as context and ask it to walk you through each phase. The agent can help you run commands, explain concepts, and debug issues — but always review cost-related actions yourself before approving them.

---

## Phase 1: Understand the Concepts (No Code Required)

**Goal**: Understand what this project does, why it exists, and what all the terminology means — without touching any code.

### Read

1. [README.md](../README.md) — top to bottom. Focus on the "Key Concepts" section.
2. [docs/GLOSSARY.md](GLOSSARY.md) — every term. Bookmark this for reference.
3. The [SWE-bench Pro paper abstract](https://arxiv.org/abs/2509.16941) — just the abstract, to understand the research motivation.
4. [Dataset & Attribution](../README.md#dataset--attribution) section of the README — understand where the tasks come from.

### Key Questions You Should Be Able to Answer

- What is SWE-bench Pro and who created it?
- What does "fail-to-pass" mean? Why do we need tests to fail *before* the agent runs?
- What does "pass-to-pass" mean? Why do we check for regressions?
- What is a "task" in this project? What three files define one?
- Why do evaluations run in Docker containers?
- What is the difference between Claude, Codex, and Gemini in this context?
- Roughly how much does a single evaluation task cost?

### Checkpoint

Explain to a friend (or your AI agent) in 2-3 sentences what this project does. If you can do that, move on.

---

## Phase 2: Explore the Codebase (Read-Only)

**Goal**: Navigate the repository confidently. Know where things live and how they connect.

### Read

1. [docs/ARCHITECTURE.md](ARCHITECTURE.md) — the full pipeline, from dispatch to artifacts.
2. [docs/TASK-SCHEMA.md](TASK-SCHEMA.md) — how tasks are defined.

### Do

Run these commands locally (no API keys needed, no cost):

```bash
# Clone the repo
git clone https://github.com/thecontextlab/swebench-pro-runner.git
cd swebench-pro-runner

# See the top-level structure
ls -la

# Count how many repos have datasets
ls datasets/

# Count total tasks across all repos
find datasets/*/tasks -name "*.yaml" | wc -l

# Read one task definition
cat datasets/vuls/tasks/future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c.yaml

# Read the matching setup and run scripts
cat datasets/vuls/tasks/future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c.setup.sh
cat datasets/vuls/tasks/future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c.run_script.sh

# Look at a repository config
cat datasets/vuls/config.yaml

# Look at an agent wrapper
cat datasets/vuls/run_claude.py

# See what orchestration scripts exist
ls scripts/eval-orchestration/

# Look at the workflow
cat .github/workflows/swebench-eval.yml
```

### Exercises

1. **Pick three different repos** (one Go, one Python, one TypeScript) and compare their `config.yaml` files. What's the same? What's different?
2. **Compare `run_script.sh`** files across a Go repo (`vuls`) and a Python repo (`ansible`). How does test execution differ?
3. **Read `datasets/common/config_loader.py`** — trace how a task ID gets resolved to a Docker image. What are the three levels of the hierarchy?

### If You're Using an AI Agent

Ask your AI agent:
- "Walk me through the evaluation pipeline step by step, referencing the actual workflow YAML"
- "How does `run_claude.py` in the vuls dataset work?"
- "What's the difference between `setup.sh` and `run_script.sh`?"

### Checkpoint

You should be able to draw a diagram (even on paper) showing: `task YAML → workflow → Docker container → agent runs → tests → result.json`. If the flow makes sense, move on.

---

## Phase 3: Run Your First Evaluation (Costs Money)

**Goal**: Run a single task end-to-end, download the result, and understand every field.

### Prerequisites

Before proceeding, make sure you have:

- [ ] Forked the repository on GitHub
- [ ] GitHub CLI installed and authenticated (`gh auth login`)
- [ ] At least one API key set as a repository secret (Settings → Secrets and variables → Actions)
- [ ] Read the [Cost Warning](../README.md#cost-warning) section

### Do

**Step 1: Run one task** (estimated cost: ~$0.15-$0.50 with Claude Sonnet)

```bash
gh workflow run swebench-eval.yml \
  -f repo=vuls \
  -f task="future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c" \
  -f agent=claude \
  -f model="claude-sonnet-4-5-20250929" \
  -f enable_mcp=false
```

**Step 2: Monitor** (refresh every few minutes — takes 5-45 minutes)

```bash
gh run list --workflow=swebench-eval.yml --limit=5
```

Look for: `completed` status and `success` or `failure` conclusion.

**Step 3: Download the result**

```bash
# Get the run ID from the output of step 2 (first column)
gh run download <run-id>
```

**Step 4: Inspect the result**

```bash
# Pretty-print the result JSON
python3 -m json.tool results/result.json

# Check: was the task resolved?
python3 -c "import json; r=json.load(open('results/result.json')); print(f'Resolved: {r.get(\"resolved\")}, Cost: \${r.get(\"total_cost_usd\", 0):.2f}')"
```

**Step 5: Read the verification logs**

```bash
# Pre-verification: these tests should have FAILED (that's correct!)
cat results/pre_verification.log

# Post-verification: these tests should have PASSED (agent fixed the bug)
cat results/verification.log
```

**Step 6: Read the agent's changes**

```bash
# What did the agent modify?
cat results/changes.patch
```

### Understanding result.json

Key fields to check:

| Field | What It Means |
|-------|---------------|
| `resolved` | `true` = agent fixed the bug without breaking anything |
| `f2p_resolved` | `true` = fail-to-pass tests now pass |
| `p2p_no_regression` | `true` = pass-to-pass tests still pass |
| `total_cost_usd` | How much this run cost in API fees |
| `duration_seconds` | Wall-clock time |
| `num_turns` | How many back-and-forth turns the agent took |
| `tokens.input` / `tokens.output` | Token consumption (drives cost) |
| `code_changes.lines_added` / `lines_removed` | Size of the agent's fix |

See [docs/ANALYTICS.md](ANALYTICS.md) for the complete schema.

### Checkpoint

You ran one task, downloaded the artifacts, and can explain whether the agent succeeded or failed and why. You know what the result cost. Move on.

---

## Phase 4: Make Your First Contribution (Low Risk)

**Goal**: Submit your first pull request. Start with something that can't break evaluations or cost money.

### Read

1. [CONTRIBUTING.md](../CONTRIBUTING.md) — the full contributing guide, including "Things to Avoid" and "Good First Contributions"

### Pick a Starter Task

Choose one of these (sorted by difficulty):

#### Easy: Verify task counts

```bash
# Count YAML files per repo and compare to the README table
for repo in datasets/*/; do
  repo_name=$(basename "$repo")
  count=$(find "$repo/tasks" -name "*.yaml" 2>/dev/null | wc -l | tr -d ' ')
  echo "$repo_name: $count tasks"
done
```

Does the total match 742? Do individual repo counts match the README table? If not, submit a PR fixing the README.

#### Easy: Validate all YAML files

```bash
# Check every task YAML parses correctly
python3 -c "
import yaml, glob, sys
errors = []
for f in sorted(glob.glob('datasets/*/tasks/*.yaml')):
    try:
        yaml.safe_load(open(f))
    except Exception as e:
        errors.append((f, str(e)))
for f, e in errors:
    print(f'ERROR: {f}: {e}')
print(f'\nChecked {len(glob.glob(\"datasets/*/tasks/*.yaml\"))} files, {len(errors)} errors')
"
```

#### Medium: Document your onboarding experience

Follow this very guide, take notes on where you got stuck, and submit a PR improving the docs.

### Your First PR Workflow

```bash
# Create a branch
git checkout -b your-username/fix-task-counts

# Make your changes
# ...

# Commit
git add -A
git commit -m "Fix task counts in README"

# Push
git push -u origin your-username/fix-task-counts

# Create the PR
gh pr create --title "Fix task counts in README" --body "Updated task counts to match actual YAML files in datasets/"
```

### Checkpoint

You submitted a PR and it got reviewed (or is awaiting review). You understand the contribution flow. Move on.

---

## Phase 5: Deeper Contributions

**Goal**: Take on more impactful work. At this point you understand the system well enough to make meaningful changes.

### Contribution Paths

Choose based on your interests and skills:

#### Path A: Task Quality (Python + domain knowledge)

- Write a YAML schema validator that checks required fields (not just syntax)
- Audit task definitions for missing `pass_to_pass` tests
- Improve `setup.sh` scripts to be more robust
- Add new tasks for existing repositories

**Read**: [TASK-SCHEMA.md](TASK-SCHEMA.md) (if you haven't fully studied it)

#### Path B: Orchestration & Analytics (Python)

- Improve error messages and `--help` output in orchestration scripts
- Add a pre-launch cost estimator to `launch_tasks.py`
- Enhance `generate_report.py` with new visualizations
- Add a `--max-tasks` safety limit to `launch_tasks.py`

**Read**: [EVAL-ORCHESTRATION.md](EVAL-ORCHESTRATION.md), [ANALYTICS.md](ANALYTICS.md)

#### Path C: Agent Integration (Python + LLM knowledge)

- Study how `run_claude.py`, `run_codex.py`, `run_gemini.py` differ
- Improve agent wrappers (add `--max-turns`, better error handling)
- Add a new agent integration
- Compare agent performance across models

**Read**: [ARCHITECTURE.md](ARCHITECTURE.md) multi-agent section

#### Path D: Infrastructure (Docker + GitHub Actions)

- Improve workflow reliability
- Add CI checks for PRs (YAML validation, linting)
- Add concurrency controls to workflows
- Study Docker image construction

**Read**: [DOCKER-IMAGES.md](DOCKER-IMAGES.md), both workflow YAML files

### Cost Awareness at Scale

As you work on larger contributions, keep cost in mind:

| Action | Estimated Cost | Think Before... |
|--------|---------------|-----------------|
| Run 1 task (Sonnet) | $0.15-$0.50 | Just run it |
| Run 1 task (Opus) | $1-$5 | Make sure you need Opus |
| Run 10 tasks (Sonnet) | $2-$5 | Use `--dry-run` first |
| Run 1 repo (Sonnet) | $15-$50 | Plan your batch, set `--delay 60` |
| Run all 742 (Sonnet) | ~$250 | Discuss with maintainers first |
| Run all 742 (Opus) | ~$2,000+ | Get explicit approval |
| Best-of-3 all tasks | 3x above | Reserved for official benchmark runs |

---

## For AI Coding Agents

If you're an AI agent helping a human contributor, here's what you need to know:

### Your Context

- `CLAUDE.md` in the repo root gives you the architecture overview
- This project evaluates AI agents on software engineering tasks — you are being used to contribute to the tool that evaluates tools like you

### What You Can Safely Do

- Read and explain any file in the repository
- Write and validate YAML task definitions
- Write Python scripts (orchestration, validation, analysis)
- Edit documentation
- Run local validation commands (YAML parsing, file counting, `--dry-run`)

### What Requires Human Approval

- Any `gh workflow run` command (costs money)
- Any change to `.github/workflows/` (can break all evaluations)
- Any change to `datasets/common/` (affects all 11 repositories)
- Any `launch_tasks.py` command without `--dry-run`
- Pushing to remote branches

### Useful Prompts for the Human to Give You

- "Walk me through how [filename] works"
- "What would happen if I changed [X] in [file]?"
- "Write a YAML schema validator for task files"
- "Help me understand why task [ID] failed — here's the result.json: [paste]"
- "Compare the run_claude.py across vuls and ansible — what's different?"
- "Dry-run: show me what `launch_tasks.py` would do with this task file"

### Key Files to Read First

1. `CLAUDE.md` — your architecture briefing
2. `docs/GLOSSARY.md` — terminology
3. `datasets/common/config_loader.py` — configuration resolution
4. `datasets/common/base_agent_adapter.py` — agent base class
5. `.github/workflows/swebench-eval.yml` — the evaluation pipeline
6. Any `datasets/{repo}/config.yaml` — repository-level config

---

## Getting Help

- **Stuck on a concept?** Check [GLOSSARY.md](GLOSSARY.md) first, then the relevant doc from the [Documentation table](../README.md#documentation).
- **Stuck on a command?** Most orchestration scripts support `--help`: `python3 scripts/eval-orchestration/launch_tasks.py --help`
- **Found a bug?** Open an issue with the task ID, repository name, and what you expected vs. what happened.
- **Want to discuss an approach?** Open an issue or discussion before starting large changes — especially anything that touches workflows or agent wrappers.
