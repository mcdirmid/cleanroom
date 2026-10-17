<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_workspace interface specification
CODE_HASH: 83721aa83409
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# antigravity_workspace interface component

imports: session

## Purpose

The antigravity_workspace interface component defines data types and operational contracts for configuring and confining isolated role workspaces within Google Antigravity.

Autonomous agents operating within shared project environments can inadvertently read un-blinded counterpart implementations or mutate files outside their assigned roles. The antigravity_workspace interface component formalizes boundary configuration, isolation rule synthesis, and workspace confinement reporting to guarantee that subagents remain physically and rule-constrained to their provisioned role roots.

**Out of scope:** The antigravity_workspace interface component does not execute agent turns or evaluate DAG work queues; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *workspace confinement report* captures the configured isolation state of a role workspace, including the target workspace directory, generated rule paths, role name, and confinement status.

A system's *antigravity workspace configurer* establishes Antigravity-specific isolation rules and workspace configuration within provisioned role workspaces.

When configuring a role workspace:

- The antigravity workspace configurer writes workspace-local isolation rules instructing agents never to access or modify paths outside the role workspace root.

- The antigravity workspace configurer generates role guidance documentation directing the agent to use local bin scripts for acquiring and submitting work.

- The antigravity workspace configurer produces a confinement report documenting all configured boundary files.
