<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_workspace_impl implementation specification
CODE_HASH: c34cdd8a5e6e
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# antigravity_workspace_impl implementation component

imports: agent_session, antigravity_ext, antigravity_workspace, workspace_registry
implements: antigravity_workspace

## Purpose

The antigravity_workspace_impl implementation component realizes boundary configuration and workspace-local isolation rule synthesis for Google Antigravity role workspaces.

Autonomous subagents require explicit prompt rules and filesystem boundaries to prevent unintentional access to sibling workspaces or canonical repository sources. The antigravity_workspace_impl implementation component generates isolation rules directly inside the provisioned workspace and records confinement reports.

**Out of scope:** The antigravity_workspace_impl implementation component does not execute agent turns or evaluate DAG work queues; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; platform schema conventions are delegated to antigravity_ext; interface definitions are delegated to antigravity_workspace; role definition resolution is delegated to workspace_registry.

## Types and Behavior

The antigravity workspace configurer realization establishes Antigravity-specific isolation rules and workspace configuration within provisioned role workspaces.

When configuring a role workspace:

- The realization writes isolation rules into the workspace-local rules directory forbidding navigation and modifications outside the workspace directory.

- The realization synthesizes role guidance instructions incorporating verification and submission protocols.

- The realization returns a confinement report containing relative paths of all created configuration files.
