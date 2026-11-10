# Autofab CLI Reference & Invocation Guide

Autofab is a literate, specification-driven software engineering framework for autonomous AI pair programming, double-blind verification, and deterministic DAG convergence.

All operations in the repository are invoked via **`uv run autofab <command>`**.

______________________________________________________________________

## 1. Quick Start

### Autonomous Pair-Programming (`clean`)

`autofab clean` is the primary entry point for converging software components. It evaluates dirty nodes across your project's dependency DAG, commissions isolated double-blind workspaces, and coordinates autonomous subagents to converge every node clean.

```bash
# Clean an entire package scope across all roles in topological order
uv run autofab clean my_project

# Clean a package scope up to a specific role boundary (e.g., up to planning or lib)
uv run autofab clean my_project#planning
uv run autofab clean my_project#lib

# Clean a specific component target node or implementation file
uv run autofab clean //my_project/parts/agent:agent_config#lib
uv run autofab clean my_project/parts/agent/lib/agent_config.py

# Select an explicit model profile defined in model_configs.toml
uv run autofab clean my_project --model gemini-flash
uv run autofab clean my_project --model deepseek-flash
```

> [!NOTE]
> **Runtime Harness Resolution**: Harnesses are resolved automatically from your model profile in `model_configs.toml`. For example, `gemini-flash` uses the Google Antigravity harness, while `deepseek-flash` uses the DeepSeek Harness (DSH). When cleaning with an Antigravity model, `autofab` automatically installs and refreshes the Antigravity plugin and agent definitions in `~/.gemini/config/plugins/autofab`.

### Marking Targets Dirty (`mark-dirty`)

When you want to invalidate a node, trigger downstream re-verification, or prompt agents to rework an implementation, use `mark-dirty`:

```bash
# Mark an entire scope dirty with a default reason
uv run autofab mark-dirty my_project

# Mark a specific target dirty with an actionable diagnostic reason
uv run autofab mark-dirty my_project/parts/agent/lib/agent_config.py "Type signature mismatch with low specification"
uv run autofab mark-dirty //my_project/parts/agent:agent_config#lib -m "Unit test regression on timeout handling"
```

______________________________________________________________________

## 2. Advanced & Internal Subagent Tooling

The commands below are primarily used by autonomous subagents and role workers inside isolated workspaces, or by advanced operators inspecting the DAG:

### `work-queue`

Inspects the dependency DAG and outputs ready vs. blocked tasks for a scope or role.

```bash
# Inspect all ready and blocked nodes across a scope
uv run autofab work-queue my_project

# Inspect work queue for a specific role boundary
uv run autofab work-queue my_project#lib
uv run autofab work-queue my_project#qa

# Output JSON structured task metadata (used by agent coordinators)
uv run autofab work-queue my_project --json
```

### `mark-clean`

Marks target nodes or entire directory scopes clean in metadata and DAG storage without invoking subagents.

```bash
# Mark all nodes in a scope clean
uv run autofab mark-clean my_project

# Mark a specific target clean
uv run autofab mark-clean my_project/parts/agent/lib/agent_config.py
```

### `commission` & `decommission`

Manages isolated, double-blind role workspaces (`autofab_role_workspaces/<role>_<scope>/`).

```bash
# Initialize role workspaces bound to a model profile
uv run autofab commission --all my_project --model deepseek-flash

# Decommission and delete provisioned role workspaces
uv run autofab decommission my_project
```

### `refresh-sys`

Synchronizes system tools, linters, methodology configs (`autofab_roles.toml`), and companion guides from canonical roots to provisioned role workspaces.

```bash
uv run autofab refresh-sys
```

### `get_work`

Acquires the next assigned dirty target inside an isolated role workspace.

```bash
bin/get_work
```

### `check_files`

Runs deterministic verification checks (linters, type checkers, test suites) against targets in a role workspace.

```bash
bin/check_files my_project/parts/agent/lib/agent_config.py
```

### `submit`

Verifies and submits changes for a file with in-band metadata updates (`LAST_CLEANED`, `LAST_CHANGED`, `CODE_HASH`).

```bash
bin/submit my_project/parts/agent/lib/agent_config.py "Implemented timeout helper"
```

### `blame`

Attributes an actionable defect critique or feedback to an upstream culprit contract or specification file, triggering upstream invalidation.

```bash
bin/blame my_project/parts/agent/low/agent_config.pyi "Contract missing parameter 'timeout'"
```

### `fail`

Records an unresolvable failure or impasse for a target, logging diagnostic failure details and leaving the node dirty.

```bash
bin/fail my_project/parts/agent/lib/agent_config.py "Abstract method resolution error in pytest"
```

### `coverage`

Evaluates statement test coverage between an implementation and its double-blind unit test suite.

```bash
uv run autofab coverage --impl my_project/parts/agent/lib/agent_config.py --test my_project/parts/agent/tests/agent_config_test.py -t 100.0
```

### `change` & `prompt`

```bash
# Record an explicit manual change description on a target
uv run autofab change my_project/parts/agent/lib/agent_config.py "Refactored timeout helper"

# Print the task prompt and contract instructions for a target
uv run autofab prompt //my_project/parts/agent:agent_config#lib
```

### `configure`

Scaffolds user global configuration directory `~/.config/autofab` with starter `model_configs.toml` and credentials templates.

```bash
uv run autofab configure
```

### `install-antigravity-plugin`

Installs or refreshes the Autofab Antigravity plugin and agent definitions into `~/.gemini/config/plugins/autofab`. When running `uv run autofab clean` with an Antigravity model profile, this is performed automatically.

```bash
uv run autofab install-antigravity-plugin
```

______________________________________________________________________

## 3. Target Addressing Syntax

Autofab targets can be addressed using multiple canonical notations:

| Format | Example | Description |
| :--- | :--- | :--- |
| **Fully Qualified Target** | `//my_project/parts/agent:agent_config#lib` | Exact unit and role address |
| **File Path** | `my_project/parts/agent/lib/agent_config.py` | Automatically resolved to target address |
| **Role Partition** | `my_project/parts/agent/lib` or `my_project#lib` | All units under the `lib` role |
| **Part Directory** | `my_project/parts/agent` | All roles and units under `agent` part |
| **Scope Directory** | `my_project` | Entire directory scope across all parts & roles |

______________________________________________________________________

## 4. Model Configuration Schema (`model_configs.toml`)

Autofab resolves model profiles and rate cards from:

1. Local workspace: `./model_configs.toml`
1. User global configuration: `~/.config/autofab/model_configs.toml` (default)
1. Canonical starter template: `autofab_py/templates/model_configs.toml`

Run `uv run autofab configure` to scaffold `~/.config/autofab/model_configs.toml`.

### TOML Schema

```toml
# Top-Level Configuration
default = "deepseek-flash"               # Default model profile name (harness is derived from model)
max_unproductive_rounds = 3              # Global circuit-breaker round limit

# Model Profiles: [models.<profile-name>]
[models.deepseek-flash]
model = "deepseek-flash"                 # Model identifier passed to harness
provider = "deepseek"                    # Provider adapter ("deepseek", "google", "mlx", "anthropic")
harness = "dsh"                          # Runtime harness ("dsh", "antigravity")
tier = 2                                 # Capability tier (1=Local, 2=Budget, 3=Mid-Tier, 4=Frontier)
tier_label = "Budget API"                # Descriptive capability label
rate_uncached_in = 0.15                  # USD per 1,000,000 uncached input tokens
rate_cached_in = 0.003                   # USD per 1,000,000 cached input tokens (prompt cache hit)
rate_out = 0.60                          # USD per 1,000,000 output tokens
subagent_batch_size = 10                 # Maximum concurrent role subagent dispatches
timeout_seconds = 120.0                  # Request/process timeout in seconds

[models.gemini-flash]
model = "gemini-flash"
provider = "google"
harness = "antigravity"
tier = 2
tier_label = "Budget Frontier API"
rate_uncached_in = 0.10
rate_cached_in = 0.025
rate_out = 0.40
subagent_batch_size = 5
timeout_seconds = 120.0

[models.gemini-pro]
model = "gemini-pro"
provider = "google"
harness = "antigravity"
tier = 3
tier_label = "Mid-Tier Frontier API"
rate_uncached_in = 1.25
rate_cached_in = 0.3125
rate_out = 5.00
subagent_batch_size = 5
timeout_seconds = 180.0
```
