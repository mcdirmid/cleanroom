# Control Part (`update_with_ai/parts/control`)

## Purpose

The **control** part implements the session-level coordination engine, topological task scheduler, verification runner, and defect attribution system for Cleanroom.

Autonomous software engineering workflows require discovering ready tasks dynamically across deep dependency graphs without hardcoding role lifecycle phases. When tasks fail or specifications are violated, defects must be routed back to the exact upstream specifications or contracts responsible rather than patched ad-hoc. The control part coordinates task progression: it discovers dirty nodes whose prerequisites are satisfied, dynamically schedules them by topological role tier depth, invokes and caches verification checks, enforces clean submission gates, and attributes defects back to blamed upstream nodes.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/control/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high):

- [`control_work_scheduler.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_work_scheduler.md) & [`control_work_scheduler_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_work_scheduler_impl.md): Discovers ready dirty nodes within execution subgraphs or directory scopes. It orders candidate tasks using dynamic topological *role tier depth* (so upstream roles are guaranteed to precede downstream roles without naming specific roles), formats task prompts with declared dependency paths using user-facing file aliases, and appends unaddressed historical feedback.
- [`control_verification.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_verification.md) & [`control_verification_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_verification_impl.md): Executes verification checks (such as compilers, linters, type checkers, and unit test suites) in subprocesses. It strips non-actionable compiler noise (progress bars, banners) and caches results by source file SHA-256 hash to eliminate redundant check runs on unchanged targets.
- [`control_attribution.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_attribution.md) & [`control_attribution_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_attribution_impl.md): Manages defect attribution and blame routing. When a downstream role discovers an error in an upstream specification or contract, the attribution engine validates the blamed file against declared blame targets, records the critique as unacted feedback on the owning dependency node, and marks that upstream node dirty.
- [`control_submit.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_submit.md) & [`control_submit_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_submit_impl.md): Governs target submission. It ensures all verification checks pass before allowing a node to be marked clean, clears unacted feedback, records change summaries and timestamps, and propagates change notifications to downstream dependents.
- [`control_coordinate.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_coordinate.md) & [`control_coordinate_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_coordinate_impl.md): Defines the central `SessionCoordinator` interface and implementation that ties together scheduling, verification evaluation, blame attribution, and submission gating during an active agent session.
- [`control_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/control/high/control_asm.md): Aggregates the work scheduler, verification evaluator, attribution engine, submitter, and session coordinator into the unified control service.

## How It Is Used by Other Parts

- **`sandbox`**: The agent tool implementations in `sandbox` interact directly with `control`:
  - `sandbox_run_control` delegates verification evaluation to `control_verification` during calls to `check_files`.
  - `sandbox_submission` delegates `submit`, `fail`, and `blame` execution to `control_submit` and `control_attribution` via the session coordinator.
- **`tools`**: The role workspace CLI commands and verification utilities in `tools` rely heavily on `control`:
  - `workspace_work` calls `control_work_scheduler` to discover ready tasks by role tier depth across directory scopes.
  - `workspace_check` calls `control_verification` to execute checks with noise scrubbing and source-hash caching.
- **`systems`**: Included directly in `uv_cleanroom_asm` to assemble the end-to-end Cleanroom runtime.
- **Support (`cleanroom_role_tool`)**: Uses `control` services when executing CLI commands such as `cleanroom clean` and checking task readiness.
