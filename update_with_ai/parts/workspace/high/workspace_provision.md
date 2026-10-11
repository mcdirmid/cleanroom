<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:03Z
LAST_CHANGED: 2026-10-08T18:30:00Z
CHANGE: document stub role dependencies synthesis in commissioning contract
CODE_HASH: bfbef995bc8b
SPEC_QA_AUDIT: 2026-10-11T22:09:03Z
-->

# workspace_provision interface component

imports: agent_session, workspace_registry

## Purpose

The workspace_provision interface component defines operational contracts for commissioning directory-scoped Cleanroom role workspaces with strict permission isolation and deployed runner executables.

Uncontrolled read-write access across an entire codebase leads to accidental cross-tier modifications, out-of-scope code drift, and unintended edits to upstream contracts. Autonomous agents require hermetic environments where upstream contracts are strictly immutable, target files are explicitly bounded, and interaction is mediated through dedicated helper tools. The workspace_provision interface component establishes contracts for creating isolated role workspace trees, copying target and contract files with read-only permission enforcement (`chmod 444`), and deploying self-contained runner tools into `bin/`.

**Out of scope:** The workspace_provision interface component does not harvest code changes to the main repository, calculate topological task dirty queues, or evaluate code coverage; these are handled by other components.

**Delegated:** Role metadata resolution, workspace path calculation, and registry updates are delegated to workspace_registry.

## Types and Behavior

An agent session's *workspace provisioner* creates and configures directory-scoped role workspaces.

The workspace provisioner:

- Commissions an isolated role workspace for a specified role and directory scope, creating the workspace directory structure, configuring role metadata, and registering the workspace in the persistent registry.

- Copies the declared writable files of the role with read-write permissions, and copies upstream contract dependencies with read-only permissions, preventing in-place clobbering of upstream specifications.

- Synthesizes read-only test stubs that raise `NotImplementedError` from companion specifications into the workspace for roles declaring stub dependencies, rather than copying real implementations, preventing implementation leakage.

- Deploys executable runner tools into the `bin/` directory of the workspace, packaging the work, submit, blame, fail, and coverage runners as executable scripts with execution permissions.

- Writes workspace role configuration into a hidden role descriptor file and synthesizes a role-tailored `AGENTS.md` guide file establishing agent constraints and tool invocation workflows.
