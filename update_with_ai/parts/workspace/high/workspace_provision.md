<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-08T18:30:00Z
CHANGE: document stub role dependencies synthesis in commissioning contract
CODE_HASH: 55adae21bff5
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_provision interface component

imports: agent_session, cleanroom_files_ext, workspace_registry

## Purpose

The workspace_provision interface component defines operational contracts for commissioning directory-scoped Cleanroom role workspaces with strict permission isolation and deployed runner executables.

Uncontrolled read-write access across an entire codebase leads to accidental cross-tier modifications, out-of-scope code drift, and unintended edits to upstream contracts. Autonomous agents require hermetic environments where upstream contracts are strictly immutable, target files are explicitly bounded, and interaction is mediated through dedicated helper tools. The workspace_provision interface component establishes contracts for creating isolated role workspace trees, copying target and contract files with read-only permission enforcement (`chmod 444`), and deploying self-contained runner tools into `bin/`.

**Out of scope:** The workspace_provision interface component does not harvest code changes to the main repository, calculate topological task dirty queues, or evaluate code coverage; these are handled by other components.

**Delegated:** Role metadata resolution, workspace path calculation, and registry updates are delegated to workspace_registry. File naming conventions for the role descriptor configuration are delegated to cleanroom_files_ext. Runner zipapp deployment, role metadata serialization, AGENTS.md guide synthesis, and missing target skeleton generation are delegated to workspace_scaffold.

## Types and Behavior

An agent session's *workspace provisioner* creates and configures directory-scoped role workspaces.

The workspace provisioner:

- Commissions an isolated role workspace for a specified role and directory scope, creating the workspace directory structure, configuring role metadata, and registering the workspace in the persistent registry.

- Copies the declared writable files of the role with read-write permissions, and copies upstream contract dependencies with read-only permissions, preventing in-place clobbering of upstream specifications.

- Copies and writes files across role workspaces, applying explicit read-only, writable, or executable permissions.

- Synthesizes read-only test stubs that raise `NotImplementedError` from companion specifications into the workspace for roles declaring stub dependencies, rather than copying real implementations, preventing implementation leakage, and synchronizes or purges test stubs to keep role workspaces aligned with companion specifications.

- Deploys executable runner tools into the `bin/` directory of the workspace, packaging the work, submit, blame, fail, and coverage runners as executable scripts with execution permissions.

- Writes workspace role configuration into a hidden role descriptor file recording role identity and optional model profile settings without exposing host repository paths, and synthesizes a role-tailored `AGENTS.md` guide file establishing agent constraints and tool invocation workflows.
