# Ground-Truth Pilot Harness

Builds + runs SWE-bench Pro tasks against the **upstream-canonical per-task Docker images** from `SWE-bench_Pro-os`, then runs vanilla Claude Code on top. Compares "agent on ground-truth infra" vs our consolidated images — definitive infra-vs-agent attribution.

Context and rationale: see `/Users/manoj/sources/bitoexperiment/phase-5-150/PHASE5_AUDIT_RESPONSE.md` (the "Ground-truth pilot proposal" section).

## Prereqs

- Docker daemon running (Apple Silicon: amd64 emulation must work; the scripts pin `--platform=linux/amd64`)
- `gh` authenticated to GHCR (only needed if you `--push` the images)
- `ANTHROPIC_API_KEY` env var (or `oauth_token` from a Claude Code session)
- `SWE-bench_Pro-os` cloned at `/Users/manoj/sources/SWE-bench_Pro-os` (or set `SWE_BENCH_PRO_OS_DIR`)

## Pilot tasks (5 strategic picks)

| # | task_id | Why |
|---|---|---|
| 1 | `internetarchive__openlibrary-03095f2680f7516fca35a58e665bf2a41f006273-v8717e18970bcdc4e0d2cea3b1527752b21e74866` | Needs Python 3.10. We have no 3.10 image — only path to validate. |
| 2 | `internetarchive__openlibrary-c12943be1db80cf1114bc267ddf4f9933aca9b28-v2c55207218fb8a0138425cbf7d9675272e240b90` | Tests whether removing setup.sh `pytest==6.2.1` pin alone suffices on a Python 3.11.1 ground-truth image. |
| 3 | `protonmail__webclients-01ea5214d11e0df8b7170d91bafd34f23cb0f2b1` | Settles the yarn-4.12 debate. If passes on ground-truth (yarn 3.x) image, our consolidated image is fine. |
| 4 | `ansible__ansible-395e5e20fab9cad517243372fa3c3c5d9e09ab2a-v7eee2454f617569fd6889f2211f75bc02a35f9f8` | Sanity-checks our `/app→/testbed` sed fix matches ground-truth behavior. |
| 5 | `future-architect__vuls-f6cc8c26a9c08a18e3d1f48dab0bbd3aaaa1e24c-v...` | Zero-state Go 1.24 task. Confirms ground-truth has Go 1.24 (and would pass). |

## Usage

### Build a per-task image

```bash
./build_instance_image.sh internetarchive__openlibrary-03095f2680f7516fca35a58e665bf2a41f006273-v8717e18970bcdc4e0d2cea3b1527752b21e74866
```

Produces `gt-base-03095f26:latest` and `gt-instance-03095f26:latest` locally. Build time ~5–15 min (full pip/npm/go install at base commit).

Optional `--push <registry/prefix>` pushes the images to a registry you control.

### Run vanilla agent on a built image

```bash
ANTHROPIC_API_KEY=sk-ant-... ./run_on_instance_image.sh internetarchive__openlibrary-03095f2680f7516fca35a58e665bf2a41f006273-v8717e18970bcdc4e0d2cea3b1527752b21e74866
```

Pipeline inside the container: install latest Claude CLI → symlink `/testbed → /app` → pre-verify F2P → pre-verify P2P → run agent → capture diff → post-verify F2P → post-verify P2P → write result.json.

Output: `/Users/manoj/sources/bitoexperiment/phase-5-150/ground_truth_pilot_results/<task_id>/`

## How it works (FROM-line rewriting)

Upstream `instance_dockerfile/<task_id>/Dockerfile` references private images:

```
FROM 084828598639.dkr.ecr.us-west-2.amazonaws.com/sweap-images/<repo>:base_<...>
```

These point at SWE-bench Pro's private AWS ECR. We sed-rewrite to the locally-built base tag:

```
FROM gt-base-<short>:latest
```

Three FROM patterns are handled in `instance_dockerfile`:
1. AWS ECR full path (most common)
2. `base_<repo>___<date>.<sha>` (logical-dated)
3. `base_<repo>` (logical-undated, e.g. vuls)

Likewise, `base_dockerfile` FROMs may use the AWS ECR mirror of public Docker Hub:

```
FROM 084828598639.dkr.ecr.us-west-2.amazonaws.com/docker-hub/library/python:3.10-slim-bookworm
```

→ rewritten to the public equivalent:

```
FROM python:3.10-slim-bookworm
```

If the FROM is already a public image (most Go/Node tasks: `golang:1.24-bookworm`, `node:22-bullseye`, etc.), the rewrite is a no-op.

## Workdir caveat: /app vs /testbed

Upstream uses **`/app`** as the workdir (`mkdir /app; WORKDIR /app; git clone … into /app`). Our existing `run_claude.py` wrappers hard-code `cwd="/testbed"`. Rather than fork the wrapper, the run script **symlinks `/testbed → /app`** inside the container. The agent sees `/testbed` paths, which dereference to `/app` content. `git -C /app diff` afterwards works because the working tree is the same.

## Other things to know

- **`pypi-timemachine` build network.** Python instance Dockerfiles run `pypi-timemachine` as a server during image build to pin pip to packages-as-of-`<date>`. Requires outbound internet at build time.
- **`PYTEST_ADDOPTS` includes `--reruns=3`** baked as ENV. Inflates wall time on flaky tests.
- **No `VERIFICATION_PHASE` semantics upstream.** The upstream `run_script.sh` doesn't distinguish pre vs post — we just invoke it twice (before and after agent) and compare exit codes.
- **Test name calling convention.** Positional args; comma-separated also OK. `instance_info.txt` provides FAIL_TO_PASS / PASS_TO_PASS as JSON arrays.

## Decision matrix for the 5-task pilot

| Pilot pass rate | Interpretation | Action |
|---|---|---|
| 4–5 pass on ground-truth | Strong infra signal — our consolidated images have significant friction | Invest in per-task image system for failing set (~30 tasks) |
| 2–3 pass | Moderate infra signal | Targeted fixes + per-task images only for residual unfixables |
| 0–1 pass | Agent-capability dominated | Stop here. Tier-1 fixes are sufficient. |

## Known TODOs

- **Apple Silicon performance.** amd64 emulation on M-series is slow (~3–5x slower than native). For the 5-task pilot, OK; for a broader investment, consider a Linux build host.
- **MCP layering not yet built.** Pilot tests vanilla agent only. If pilot is conclusive, follow-up could layer Bito skills + MCP on top to test "Bito on ground-truth image" vs "Bito on our image".
- **Result aggregation.** No batch-runner yet. For 5 tasks, run them sequentially and compare result.json by hand. If we expand, build an `audit_pilot.py` similar to `audit_artifacts.py` for the consolidated runs.
