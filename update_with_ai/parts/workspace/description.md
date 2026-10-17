# Workspace Part (`update_with_ai/parts/workspace`)

## Purpose

The **workspace** part implements role workspace provisioning, methodology role configuration loading, test stub synthesis, directory scaffolding, and atomic bi-directional file synchronization for Cleanroom.

A foundational principle of Cleanroom is strict role isolation: agents operating in one role (e.g. library implementation or unit testing) must be blind to uncontracted peer code, counterpart test implementations, and unapproved changes. The workspace part provisions isolated physical workspaces for each methodology role (e.g. `.cleanroom/role_workspaces/<role>/`), deploys workspace binaries and guides, generates read-only `NotImplementedError` test stubs from `.pyi` interface contracts to prevent implementation leaks, pulls upstream dependencies, and safely harvests verified changes back to the canonical repository via two-phase atomic synchronization with code-hash verification.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/workspace/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high):

- [`roles.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/roles.md) & [`roles_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/roles_impl.md): Loads methodology role definitions from `cleanroom_roles.toml`. Extracts role hierarchies, source file patterns, role dependencies, star role dependencies (transitive specification contracts), stub role dependencies, feedback role dependencies (blame targets for auditor roles), and role guidance documents.
- [`role_registry.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/role_registry.md) & [`role_registry_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/role_registry_impl.md): Maintains the registry of provisioned role workspaces, tracking physical workspace root paths by role name and resolving paths across workspaces.
- [`provision.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/provision.md) & [`provision_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/provision_impl.md): Provisions isolated role workspaces beneath `.cleanroom/role_workspaces/<role>/`. Sets up workspace directory layouts, packages and deploys workspace runner binaries (`get-work`, `check-files`, `submit`, `blame`, `status`), writes platform configuration files, and regenerates role guides.
- [`scaffold.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/scaffold.md) & [`scaffold_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/scaffold_impl.md): Scaffolds file and directory structures in role workspaces, instantiating starter templates for newly created targets.
- [`stub.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/stub.md) & [`stub_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/stub_impl.md): Synthesizes read-only test stubs from `.pyi` specifications. It parses AST representations, strips type annotations for compatibility, and generates read-only Python modules where functions and classes raise `NotImplementedError`. This enables test-authoring roles to write unit tests against interface signatures without observing or depending on actual implementation code.
- [`sync.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/sync.md) & [`sync_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/sync_impl.md): Governs bi-directional synchronization between the canonical repository and role workspaces:
  - **Pulling**: Copies updated upstream contracts, guides, and source files into role workspaces with strict permissions (read-only for upstream dependencies, read-write for role targets) and updates test stubs.
  - **Refreshing**: Syncs project configurations, guides, tools, and linters without modifying active work.
  - **Harvesting**: Two-phase atomic synchronization back to the canonical repository. Phase 1 scans writable targets and validates code hashes to prevent merge collisions; Phase 2 writes verified modifications and attested audit stamps.
  - **Blame Flushing**: Reads buffered blame records from local `.cleanroom/blame.json` files and flushes them directly into in-band feedback comments in canonical upstream files.
- [`workspace_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/workspace/high/workspace_asm.md): Assembles the workspace registry, role loader, provisioner, scaffolder, stub synthesizer, and synchronizer into an operational subsystem.

## How It Is Used by Other Parts

- **`subagent`**: `subagent_coordinator` uses `workspace` (`provision`, `sync`, `role_registry`) to set up isolated role workspaces before launching subagent turns, pull updated upstream files, and harvest submitted code and flushed blame critiques upon turn completion.
- **`antigravity` & `dsh`**: When provisioning workspaces for Antigravity or DeepSeek Harness, the harness adapters and workspace configurers write platform-specific isolation rules and overlay patches into the workspace root provisioned by `workspace`.
- **`tools`**: Workspace CLI commands (`get-work`, `check-files`, etc.) execute inside directories managed by `workspace`, querying `role_registry` and `roles` for active paths and role metadata.
- **`systems`**: Aggregated into `cleanroom_asm`.
- **Top-Level CLI & Support (`cleanroom_role_tool`)**: Entrypoints call `provision` and `sync` to initialize workspaces and execute synchronization operations.
