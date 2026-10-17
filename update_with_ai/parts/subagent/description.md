# Subagent Part (`update_with_ai/parts/subagent`)

## Purpose

The **subagent** part implements the multi-agent supervisor, process harness registry, and dynamic queue-driven orchestration engine for Cleanroom.

Scaling automated pair programming across complex multi-step pipelines requires coordinating specialized, autonomous subagents operating concurrently or sequentially within isolated role workspaces. The subagent part provides the supervisory orchestration loop: it discovers ready dirty targets across directory scopes, provisions role workspaces, dispatches role-specific directives through pluggable harness adapters, monitors child process lifecycles and token consumption, applies submitted targets and flushed blames back to canonical repositories, and iterates until DAG convergence or failure.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/subagent/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/subagent/high):

- [`subagent_coordinator.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/subagent/high/subagent_coordinator.md) & [`subagent_coordinator_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/subagent/high/subagent_coordinator_impl.md): Defines the multi-agent supervisor driving dynamic queue-driven process supervision.
  - Queries ready dirty nodes across directory scopes grouped by role tier depth.
  - Provisions and synchronizes isolated role workspaces before dispatch.
  - Dispatches turns to the designated harness adapter, passing structured role directives.
  - Processes turn outcomes: harvests submitted targets, flushes blame critiques to upstream contracts, and marks failing targets.
  - Loops dynamically across waves until all targets in scope converge to clean, maximum waves are reached, or fatal errors occur.
  - Tracks cumulative wall-clock time, model token usage, and financial expenditures across all child turns.
- [`subagent_harness.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/subagent/high/subagent_harness.md) & [`subagent_harness_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/subagent/high/subagent_harness_impl.md): Defines the abstract `HarnessAdapter` interface and central `HarnessRegistry`.
  - Formalizes `RoleTurnResult`: turn status (`clean`, `blamed`, `failed`), submitted targets, blamed targets, diagnostics, token metrics, and duration.
  - Implements the generic command harness adapter executing subprocess templates, interpolating workspace directories and role names, polling termination, parsing pending buffers, and reading process logs.
  - Provides the harness registry mapping platform names (e.g. `antigravity`, `dsh`, or custom command templates) to adapter factories.
- [`subagent_tool.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/subagent/high/subagent_tool.md) & [`subagent_tool_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/subagent/high/subagent_tool_impl.md): Implements the CLI command runner for `cleanroom orchestrate`. Parses directory scopes, target roles, harness platforms, model overrides, batch sizes, timeouts, and token limits, driving the coordinator and displaying summary reports.
- [`subagent_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/subagent/high/subagent_asm.md): Assembles the coordinator, harness registry, and command tool runner.

## How It Is Used by Other Parts

- **`antigravity`**: Registers the `AntigravityHarnessAdapter` into `subagent_harness`'s `HarnessRegistry`, conforming to `HarnessAdapter` and producing `RoleTurnResult` instances.
- **`dsh`**: Registers the `DshHarnessAdapter` into `subagent_harness`'s `HarnessRegistry`, conforming to `HarnessAdapter` and producing `RoleTurnResult` instances.
- **`workspace`**: `subagent_coordinator` commands `provision` and `sync` to scaffold role workspaces, pull upstream contracts, harvest modified files, and flush blame feedback between turns.
- **`tools`**: `subagent_harness` inspects `pending` and `work` buffers (`pending_work.json`, `blame.json`) to determine submitted and blamed targets.
- **Top-Level CLI & Support (`cleanroom_role_tool`)**: Dispatches the `orchestrate` CLI entrypoint directly to `subagent_tool`.
