<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_coordinator_impl implementation specification
CODE_HASH: d5c4f7252675
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# antigravity_coordinator_impl implementation component

imports: session, antigravity_coordinator, antigravity_ext, antigravity_workspace, subagent_coordinator, role_registry
implements: antigravity_coordinator, antigravity_workspace

## Purpose

The antigravity_coordinator_impl implementation component realizes skill artifact generation, tool parameter formatting, wake notification parsing, boundary configuration, and workspace-local isolation rule synthesis for Google Antigravity coordinator subagents and role workspaces.

Automated coordination requires precise prompt construction, dynamic workspace path binding, and robust completion message extraction. The antigravity_coordinator_impl implementation component formats skill markdown templates, builds subagent tool parameters, parses structured completion messages, and generates isolation rules directly inside provisioned workspaces.

**Out of scope:** The antigravity_coordinator_impl implementation component does not directly execute subagent subprocesses or mutate source files; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; interface definitions are delegated to antigravity_coordinator; skill schema conventions are delegated to antigravity_ext; role dispatch models are delegated to subagent_coordinator; role definition resolution is delegated to role_registry.

## Types and Behavior

The antigravity workspace configurer realization establishes Antigravity-specific isolation rules and workspace configuration within provisioned role workspaces.

When configuring a role workspace:

- The realization writes isolation rules into the workspace-local rules directory forbidding navigation and modifications outside the workspace directory.

- The realization synthesizes role guidance instructions incorporating verification and submission protocols.

- The realization returns a confinement report containing relative paths of all created configuration files.

The antigravity coordinator generator realization creates coordinator skills and formats subagent dispatch payloads.

When generating the coordinator skill:

- The realization renders the skill document containing YAML metadata and instructions for evaluating work queues and dispatching worker subagents.

- The realization validates that the generated skill enforces workspace directory pinning and prohibits inheriting the supervisor workspace.

- The realization maps role dispatch directives into subagent dispatch specifications with target workspace paths and task prompts instructing workers to drain ready nodes via submission, blame attribution, or failure diagnostics.

- The realization extracts action status, submitted targets, blamed targets, and failure diagnostics from subagent completion messages.
