# Cleanroom CLI Reference & Invocation Guide

Cleanroom is a literate, specification-driven software engineering framework for autonomous AI pair programming, double-blind verification, and deterministic DAG convergence.

All workspace lifecycle, inspection, submission, and execution operations in the canonical repository are invoked via **`uv run cleanroom`** (or `./bin/cleanroom` as a convenience wrapper).

---

## 1. Quick Start

### Autonomous Loop Execution (`--loop`)
To execute in-process autonomous DAG cleaning using an LLM without setting up external subagent processes, pass `--loop`:

```bash
# Clean an entire package scope across all roles in topological order
uv run cleanroom orchestrate staging --loop

# Clean a package scope up to a specific role boundary (e.g., up to planning or lib)
uv run cleanroom orchestrate staging#planning --loop
uv run cleanroom orchestrate staging#lib --loop

# Clean a specific component target node or implementation file
uv run cleanroom orchestrate //staging/parts/agent:agent_config#lib --loop
uv run cleanroom staging/parts/agent/lib/agent_config.py --loop

# Equivalent shorthand syntax for cleaning a target or scope
uv run cleanroom clean staging
uv run cleanroom clean staging#lib
uv run cleanroom clean //staging/parts/agent:agent_config#lib

# Specify a custom model configuration label or model name
uv run cleanroom orchestrate staging --loop --model default
```

### Multi-Agent Subagent Orchestration
To orchestrate multi-agent DAG convergence across isolated, double-blind role workspaces:

```bash
# Antigravity interactive pair-programming pre-flight (prints DAG state & directives)
uv run cleanroom orchestrate staging

# Orchestrate up to a specific role boundary
uv run cleanroom orchestrate staging#qa

# Headless multi-agent execution via DeepSeek Harness (DSH)
uv run cleanroom orchestrate staging --harness dsh

# Headless simulation run (useful for verification and test assertions)
uv run cleanroom orchestrate staging --harness simulation
```

---

## 2. Command Reference

### `orchestrate`
Orchestrates multi-agent convergence across topological waves until the DAG evaluates clean.

```bash
uv run cleanroom orchestrate <scope_or_target> [options]
```

Examples:
```bash
# Orchestrate full scope
uv run cleanroom orchestrate staging

# Orchestrate up to and including role boundary (e.g. qa)
uv run cleanroom orchestrate staging#qa
```

**Options:**
- `--loop`: Run autonomous in-process loop execution rather than an external subagent harness.
- `--harness <name>`: Subagent execution platform (`antigravity`, `dsh`, `simulation`, `loop`). Default: `antigravity`.
- `--model <name>`: Model profile or configuration name (e.g. `default`, `deepseek-v41-flash`, `gemini-3.8-flash`).
- `--max-waves <n>`: Maximum execution waves before stopping (default: `50`).
- `--batch-size <n>`: Maximum targets dispatched per role wave.
- `--timeout <seconds>`: Subprocess execution timeout in seconds.
- `--headless`: Run in headless mode without interactive prompting (used in automated CI environments; `--harness dsh` and `--loop` run headlessly by default).

---

### `work-queue` (alias: `queue`)
Inspects the dependency DAG and prints ready vs. blocked tasks for a scope or role.

```bash
# Inspect all ready and blocked nodes across a scope
uv run cleanroom work-queue staging

# Inspect work queue for a specific role boundary
uv run cleanroom work-queue staging#lib
uv run cleanroom work-queue staging#qa

# Output JSON structured task metadata (used by agent coordinators)
uv run cleanroom work-queue staging --json
```

---

### `mark-clean`
Marks target nodes or entire directory scopes clean in metadata and DAG storage without invoking the generative LLM loop.

```bash
# Mark all nodes in a scope clean
uv run cleanroom mark-clean staging

# Mark a specific role within a scope clean
uv run cleanroom mark-clean staging/parts/agent/lib

# Mark a specific target or file clean
uv run cleanroom mark-clean staging/parts/agent/lib/agent_config.py
uv run cleanroom mark-clean //staging/parts/agent:agent_config#lib
```

---

### `dirty`
Marks target nodes or directory scopes dirty in DAG storage, recording an optional diagnostic reason.

```bash
# Mark a scope dirty with default reason
uv run cleanroom dirty staging

# Mark a specific target dirty with an actionable reason
uv run cleanroom dirty staging/parts/agent/lib/agent_config.py "Type signature mismatch with low spec"
uv run cleanroom dirty //staging/parts/agent:agent_config#lib -m "Unit test regression"
```

---

### `submit`
Verifies and submits changes for a file to the canonical repository with in-band metadata updates (`LAST_CLEANED`, `LAST_CHANGED`, and `CODE_HASH`).

```bash
# Submit an updated implementation with verification checks
uv run cleanroom submit staging/parts/agent/lib/agent_config.py "Implement timeout property"

# Bypass verification checks during rapid authoring
uv run cleanroom submit --no-verify staging/parts/agent/high/agent_config.md "Author HLS"
```

---

### `feedback` (alias: `blame`)
Attributes an actionable defect critique or feedback to an upstream culprit contract, specification file, or DAG target node, triggering upstream invalidation and recording diagnostic feedback.

Supports both positional critique syntax and `-m / --message` flags:

```bash
# Deliver blame feedback to an upstream contract or specification file (in-band metadata mutation)
uv run cleanroom feedback staging/parts/agent/low/agent_config.pyi "Contract missing parameter 'timeout'"
uv run cleanroom feedback staging/parts/agent/low/agent_config.pyi -m "Contract missing parameter 'timeout'"

# Deliver feedback to a target node in the DAG
uv run cleanroom feedback //staging/parts/agent:agent_config#low "Contract missing parameter 'timeout'"
uv run cleanroom feedback //staging/parts/agent:agent_config#low -m "Contract missing parameter 'timeout'"

# 'blame' is supported as a direct alias
uv run cleanroom blame staging/parts/agent/low/agent_config.pyi "Contract missing parameter 'timeout'"
```

---

### `fail`
Records a verification failure for a target, forcing it into a dirty state with captured diagnostic failure logs.

```bash
uv run cleanroom fail staging/parts/agent/lib/agent_config.py "Abstract method resolution error in pytest"
```

---

### `check_files` (alias: `check-files`)
Runs role-specific deterministic verification checks (HLS prose linter, Planning epistemic linter, Low Pyright type checks, or unit test runners).

```bash
# Run verification checks on a specific target
uv run cleanroom check_files staging/parts/agent/lib/agent_config.py

# Run checks across pending work in the active scope
uv run cleanroom check_files
```

---

### `coverage`
Evaluates statement test coverage between an implementation and its double-blind test suite.

```bash
# Assert 100% test coverage on a module
uv run cleanroom coverage --impl staging/parts/agent/lib/agent_config.py --test staging/parts/agent/tests/agent_config_test.py -t 100.0

# Output coverage metrics in JSON
uv run cleanroom coverage staging/parts/agent:agent_config --json
```

---

### `change` & `prompt`
```bash
# Record an explicit manual change description on a target
uv run cleanroom change staging/parts/agent/lib/agent_config.py "Refactored timeout helper"

# Print the task prompt and contract instructions for a target
uv run cleanroom prompt //staging/parts/agent:agent_config#lib
```

---

### `commission` & `decommission`
Manages isolated, double-blind role workspaces (`role_workspaces/<scope>_<role>/`).

`commission` provisions and initializes role workspaces—binding model configurations, configuring harness-specific agent instructions (`AGENTS.md` and overlay patches), copying system files, and deploying role guides and tool wrappers—**without executing the subagent or running any LLM loop**:

```bash
# Initialize all declared role workspaces for a scope bound to a specific model profile without executing
uv run cleanroom commission --all staging --model deepseek-v41-flash

# Initialize role workspaces tailored for DeepSeek Harness (DSH)
uv run cleanroom commission --all staging --harness dsh --model deepseek-v41-flash

# Initialize a single role workspace bound to a specific model and harness
uv run cleanroom commission staging#lib --harness antigravity --model deepseek-v41-flash
uv run cleanroom commission staging#qa --harness dsh --model deepseek-v41-flash

# Reset an existing role workspace back to a clean state
uv run cleanroom commission staging#lib --reset

# Decommission and delete provisioned workspaces for a scope (or up to a role)
uv run cleanroom decommission staging
uv run cleanroom decommission staging#lib
```

---

### `refresh-sys`
Synchronizes system tools, linters, methodology configs (`cleanroom_roles.toml`), and guides from canonical roots to provisioned role workspaces.

```bash
uv run cleanroom refresh-sys
```

---

### `install-plugin`
Installs or refreshes the Cleanroom Antigravity extension, subagent role definitions, and coordinator tools into `~/.gemini/antigravity`.

```bash
uv run cleanroom install-plugin
```

---

## 3. Target Addressing Syntax

Cleanroom targets can be addressed using multiple canonical notations:

| Format | Example | Description |
| :--- | :--- | :--- |
| **Fully Qualified Target** | `//staging/parts/agent:agent_config#lib` | Exact unit and role address |
| **File Path** | `staging/parts/agent/lib/agent_config.py` | Automatically resolved to target address |
| **Role Partition** | `staging/parts/agent/lib` or `staging#lib` | All units under the `lib` role |
| **Part Directory** | `staging/parts/agent` | All roles and units under `agent` part |
| **Scope Directory** | `staging` | Entire directory scope across all parts & roles |

---

## 4. Test Suite Execution

To run repository verification checks, static type checks, and pytest suites cleanly:

```bash
bin/test
```

---

## 5. Model Configuration Schema (`model_configs.toml`)

Cleanroom resolves model definitions, capability tiers, and financial rate cards from:
1. Explicit CLI flag: `--model-config <path>` or `CLEANROOM_MODEL_CONFIG_FILE` environment override
2. Local repository candidate: `./model_configs.toml`
3. Canonical user configuration: `~/.config/cleanroom/model_configs.toml`
4. Canonical starter template: [`update_python_with_ai/templates/model_configs.toml`](update_python_with_ai/templates/model_configs.toml)

Run `uv run cleanroom configure` to scaffold `~/.config/cleanroom/model_configs.toml` and credentials templates.

### TOML Schema Reference

```toml
# Top-Level Harness Defaults
default = "qwen-moe-q6"                  # Default model profile name
loop_default = "qwen-moe-q6"             # Default for autonomous loop harness
antigravity_default = "gemini-4-argon"   # Default for Antigravity harness
dsh_default = "deepseek-v41-flash"       # Default for DeepSeek Harness (DSH)
max_unproductive_rounds = 5              # Global circuit-breaker round limit

# Model Profiles: [models.<profile-name>]
# IMPORTANT: Model keys containing dots must be quoted in TOML, e.g. [models."gemini-3.8-flash"]

[models.deepseek-v41-flash]
model = "deepseek-flash"                 # Model identifier sent to provider API
provider = "deepseek"                    # Protocol adapter ("deepseek", "google", "openai", "anthropic", "mlx", "omlx")
tier = 2                                 # Capability tier (1=Local, 2=Budget, 3=Mid-Tier, 4=Frontier)
tier_label = "Budget API"                # Descriptive capability label
rate_uncached_in = 0.15                  # USD per 1,000,000 uncached input tokens
rate_cached_in = 0.003                   # USD per 1,000,000 cached input tokens (prompt cache hit)
rate_out = 0.60                          # USD per 1,000,000 output tokens (including reasoning tokens)
default_harness = "dsh"                  # Recommended runtime harness ("dsh", "antigravity", "loop")
base_url = "https://api.deepseek.com/v1" # HTTP base endpoint
api_key_env = "DEEPSEEK_API_KEY"         # Environment variable holding the API key
max_tokens = 8192                        # Max completion tokens per request
subagent_batch_size = 10                 # Maximum concurrent role subagent dispatches
conversation_max_tokens = 256000         # Context window compaction threshold in tokens
max_feedback_chars = 4000                # Max feedback buffer length preserved across rounds
max_unproductive_rounds = 5              # Profile-level circuit breaker
temperature = 0.7                        # Generation temperature
timeout_seconds = 120.0                  # Request/process timeout in seconds
```

