# Task Schema Reference

Task definitions in this repository are derived from the [SWE-bench Pro](https://arxiv.org/abs/2509.16941) public dataset by Scale AI ([ScaleAI/SWE-bench_Pro](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro)). Each dataset entry is expanded into three files that together specify the problem, environment, and verification criteria.

## File Naming Convention

Each task produces three files in `datasets/{repo}/tasks/`:

```
{org}__{repo}-{commit_hash}.yaml          # Task definition
{org}__{repo}-{commit_hash}.setup.sh      # Environment provisioning
{org}__{repo}-{commit_hash}.run_script.sh # Test execution
```

Some tasks include a version suffix when they target a specific environment variant:

```
{org}__{repo}-{commit_hash}-v{version_hash}.yaml
```

**Examples:**
```
future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c.yaml
ansible__ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8-v30a923fb5c164d6cd18280c02422f75e611e8fb2.yaml
```

The `{commit_hash}` portion uniquely identifies the task and is used throughout the pipeline as the task ID.

## Task YAML Schema

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `slug` | string | Full task identifier (matches filename without `.yaml`) |
| `title` | string | Human-readable title |
| `repo` | string | Repository short name (e.g., `vuls`, `ansible`) |
| `repo_url` | string | Clone URL for the target repository |
| `instruction` | string | Problem statement given to the AI agent |
| `swebench` | object | SWE-bench metadata (see below) |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `agent_role` | string | Agent role hint (e.g., `coding`) |
| `categories` | list | Task categories (e.g., `bug-fix`, `backend`) |
| `difficulty` | string | `easy`, `medium`, `hard` |
| `description` | string | Detailed description (may differ from instruction) |
| `environment.docker_image` | string | Override Docker image for this task |
| `environment.workdir` | string | Working directory (default: `/testbed`) |
| `success_checks` | list | Legacy test commands (superseded by `swebench` section) |

### The `swebench` Section

This is the core of every task definition.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `instance_id` | string | Yes | SWE-bench instance identifier |
| `base_commit` | string | Yes | Git commit to reset the repo to before testing |
| `fail_to_pass` | list[string] | Yes | Tests that must fail before fix, pass after |
| `pass_to_pass` | list[string] | No | Tests that must pass both before and after fix |
| `before_repo_set_cmd` | string | Yes | Git commands to set up the repository state |
| `patch` | string | No | Reference solution patch (git diff format) |
| `test_patch` | string | No | Test code that gets applied via `before_repo_set_cmd` |
| `requirements` | string | No | Natural language requirements for the fix |
| `interface` | string | No | Notes on interface changes |
| `repo_language` | string | No | Primary language of the repository |
| `selected_test_files_to_run` | list | No | Subset of tests for targeted execution |
| `issue_specificity` | string | No | Issue type classification |
| `issue_categories` | list | No | Knowledge domains required |

### Example Task YAML

```yaml
slug: future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c
title: vuls - future-architect__vuls-0144135
repo: vuls
repo_url: https://github.com/future-architect/vuls.git
agent_role: coding
categories:
  - bug-fix
  - backend
difficulty: hard

instruction: |
  SNMP2CPE fails to emit correct CPEs for Fortinet FortiSwitch-108E.
  When the physical name includes a product prefix (e.g. FS_) and the
  software revision contains a product name and version, the converter
  should emit hardware, OS, and firmware CPEs.

swebench:
  instance_id: instance_future-architect__vuls-01441351c3407abfc21c48a38e28828e1b504e0c
  base_commit: 4a28722e4aa14f1d125ae789b9966c658d60c0ed
  fail_to_pass:
    - TestConvert
    - TestConvert/FortiSwitch-108E
  pass_to_pass:
    - TestConvert/Cisco_NX-OS_Version_7.1(4)N1(1)
    - TestConvert/FortiGate-50E
    - TestConvert/FortiGate-60F
    - TestConvert/YAMAHA_RTX1000
  before_repo_set_cmd: |
    git reset --hard 4a28722e4aa14f1d125ae789b9966c658d60c0ed
    git clean -fd
    git checkout 4a28722e4aa14f1d125ae789b9966c658d60c0ed
    git checkout 01441351c3407abfc21c48a38e28828e1b504e0c -- contrib/snmp2cpe/pkg/cpe/cpe_test.go
  patch: "diff --git a/contrib/snmp2cpe/pkg/cpe/cpe.go ..."
  test_patch: "diff --git a/contrib/snmp2cpe/pkg/cpe/cpe_test.go ..."
  repo_language: go
```

## The `before_repo_set_cmd` Field

This multiline string contains git commands executed before anything else. It establishes the repository state the agent will work with.

### Common Patterns

**Standard reset + test checkout:**
```
git reset --hard {base_commit}
git clean -fd
git checkout {base_commit}
git checkout {task_commit} -- path/to/test_file.go
```

This pattern:
1. Resets the repo to the base commit (before the fix)
2. Cleans untracked files
3. Checks out the test file from the task commit (so tests exist but the fix doesn't)

**With test patch application:**
```
git reset --hard {base_commit}
git clean -fd
git apply /tmp/test.patch
```

**Multiple test file checkouts:**
```
git reset --hard {base_commit}
git clean -fd
git checkout {commit} -- test/units/modules/test_foo.py
git checkout {commit} -- test/units/modules/test_bar.py
```

## Setup Scripts (`*.setup.sh`)

Setup scripts provision the environment after `before_repo_set_cmd` runs but before tests execute. They run inside the Docker container at `/setup.sh`.

### Structure

```bash
#!/bin/bash
set -e
cd /testbed

# Language-specific provisioning
```

### Go Repository Pattern

```bash
#!/bin/bash
set -e
cd /testbed

# Download dependencies
go mod download

# Optional: build verification
# go build -v ./...
```

### Python Repository Pattern

```bash
#!/bin/bash
set -e
cd /testbed

# Activate virtual environment if present
source /opt/venv/bin/activate 2>/dev/null || true

# Install in development mode
pip install -e . 2>/dev/null || true

# Install test dependencies
pip install pytest pytest-xdist 2>/dev/null || true

export PYTHONPATH=/testbed:$PYTHONPATH
export PATH=/testbed/bin:$PATH
```

### Node.js Repository Pattern

```bash
#!/bin/bash
set -e
cd /testbed

# Install dependencies
npm ci --prefer-offline 2>/dev/null || npm install

# Build if needed
npm run build 2>/dev/null || true
```

## Run Scripts (`*.run_script.sh`)

Run scripts execute verification tests. They are called by the workflow with test names as arguments and must exit with code 0 on success, non-zero on failure.

### Architecture

Every run script implements two functions:

```bash
run_all_tests()      # Called with no arguments
run_selected_tests() # Called with specific test names
```

The script dispatches based on arguments:

```bash
if [ $# -eq 0 ]; then
    run_all_tests
    exit $?
fi

# Parse comma-separated or space-separated test names
if [[ "$1" == *","* ]]; then
    IFS=',' read -r -a TEST_FILES <<< "$1"
else
    TEST_FILES=("$@")
fi

run_selected_tests "${TEST_FILES[@]}"
```

### Environment Variable

The `VERIFICATION_PHASE` environment variable is set to `pre` or `post` by the workflow, allowing scripts to adjust behavior or logging.

### Framework-Specific Patterns

#### Go (`go test`)

Used by: vuls, flipt, navidrome

```bash
run_selected_tests() {
  local test_names=("$@")

  # Detect Go packages containing the test functions
  local pkgs=()
  for test_name in "${test_names[@]}"; do
    local func_name="${test_name%%/*}"
    local test_file
    test_file=$(grep -rl "func ${func_name}(" --include="*_test.go" . 2>/dev/null | head -1)
    if [ -n "$test_file" ]; then
      local pkg_dir="./$(dirname "${test_file#./}")"
      pkgs+=("$pkg_dir")
    fi
  done

  # Build regex pattern for -run flag
  local regex_pattern="^($(IFS='|'; echo "${test_names[*]}"))$"
  go test -short -v -run "$regex_pattern" "${pkgs[@]}" 2>&1
}
```

Key detail: The script auto-detects which Go packages contain the requested tests, avoiding build failures from unrelated packages.

#### Go Custom (Teleport)

Used by: teleport

Teleport uses a custom test runner that wraps `go test` with additional reporting. The run script handles "test does not exist" as an expected condition:

```
EXPECTED: Test function TestName does not exist yet
```

#### pytest

Used by: ansible, openlibrary, qutebrowser

```bash
run_selected_tests() {
  local test_files=("$@")
  cd /testbed
  export PYTHONPATH=/testbed:$PYTHONPATH

  for test_file in "${test_files[@]}"; do
    echo "Running test: $test_file"
    python -m pytest -xvs "$test_file" 2>&1
  done
}
```

For ansible specifically, tests run through `ansible-test units` rather than raw pytest.

#### Jest

Used by: element-web

Test names use pipe-delimited format: `test/file.tsx | Suite Name | test description`

```bash
run_selected_tests() {
  for test in "$@"; do
    local test_file=$(echo "$test" | cut -d'|' -f1 | xargs)
    npx jest --no-coverage "$test_file" 2>&1
  done
}
```

#### Jest Workspace

Used by: webclients

Similar to Jest but handles monorepo workspace resolution. Test output is delimited with markers:
- `Running test: {test_name}` — section start
- `Test execution completed for {test_name}` — success
- `Test execution failed for {test_name}` — failure

#### Mocha

Used by: NodeBB

```bash
run_selected_tests() {
  for test in "$@"; do
    local test_file=$(echo "$test" | cut -d'|' -f1 | xargs)
    npx mocha "$test_file" --reporter json 2>&1
  done
}
```

Test names use pipe-delimited format: `test/file.js | Suite Name | test description`

Mocha outputs JSON with a `tests` array containing `title`, `fullTitle`, and `err` fields.

#### Custom (Tutanota)

Used by: tutanota

Tutanota uses a custom test runner. Results are identified by patterns:
- `All N assertions passed` — all tests pass
- `N out of M assertions failed` — some tests fail

## Test Name Formats

Different repositories use different test name formats in `fail_to_pass` and `pass_to_pass`:

| Framework | Format | Example |
|-----------|--------|---------|
| Go | `TestFunctionName` or `TestFunction/SubTest` | `TestConvert/FortiSwitch-108E` |
| pytest | `path/to/test.py::TestClass::test_method` | `test/units/modules/test_copy.py::TestCopy::test_copy` |
| Jest | `test/file.tsx \| Suite \| description` | `test/components/App.test.tsx \| App \| renders` |
| Mocha | `test/file.js \| Suite \| description` | `test/topics.js \| Topics \| should create` |
| Custom | Varies | `test_assertions` |

## Adding a New Task

1. **Create the YAML file** with all required `swebench` fields
2. **Create the setup script** for environment provisioning
3. **Create the run script** with `run_all_tests()` and `run_selected_tests()` functions
4. **Verify locally** that:
   - `before_repo_set_cmd` produces the correct git state
   - `setup.sh` provisions the environment without errors
   - F2P tests fail at the base commit
   - Applying the patch makes F2P tests pass
   - P2P tests pass both before and after the patch

```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('datasets/{repo}/tasks/{task_id}.yaml'))"

# Verify test names match run_script expectations
yq '.swebench.fail_to_pass[]' datasets/{repo}/tasks/{task_id}.yaml
```

## Configuration Hierarchy

Tasks can override their Docker image through three levels (highest priority first):

1. **Task-specific override** in `config.yaml` → `task_overrides.{task_id}.image`
2. **Task group pattern** in `config.yaml` → `task_groups.{group}.image` (regex match)
3. **Repository default** in `config.yaml` → `image`

This is handled by `datasets/common/config_loader.py` (`TaskImageResolver`). See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

### Task Group Example

```yaml
# datasets/ansible/config.yaml
task_groups:
  python39_legacy:
    image: ghcr.io/thecontextlab/swebench-pro-ansible:multi-agent
    pattern: "ansible__ansible-.*-v(ba6da65a|1055803c)"
    python_version: "3.9"

  python311_modern:
    image: ghcr.io/thecontextlab/swebench-pro-ansible-python311:multi-agent
    pattern: "ansible__ansible-.*-v(30a923fb|0f01c69f)"
    python_version: "3.11"
```

Task groups use regex patterns against the task ID to route tasks to appropriate Docker images. This is essential for repositories like ansible that require different Python versions for different task vintages.
