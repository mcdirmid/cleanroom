<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T09:50:00Z
CHANGE: author goose_workspace interface specification
CODE_HASH: 3060ea4ada6b
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# goose_workspace interface component

imports: agent_session

## Purpose

The goose_workspace interface component defines data types and operational contracts for configuring and confining isolated role workspaces for Goose through role instructions.

Autonomous agents operating inside role workspaces require explicit boundary guidance to prevent exploratory directory walking and cross-role file modifications. Without workspace-local instruction guidance, Goose agents may attempt unauthorized shell operations or inspect unblinded counterpart code. The goose_workspace interface component formalizes boundary configuration, instruction tailoring within role agent documentation, and confinement reporting for Goose role workspaces.

**Out of scope:** The goose_workspace interface component does not execute agent turns or evaluate DAG work queues; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *goose confinement report* captures the isolation state of a role workspace, including the workspace directory, assigned role name, configured file sequence, and status indicator.

The *goose workspace configurer* of an agent session customizes role workspace instructions and boundary constraints for Goose.

When configuring a role workspace:

- The goose workspace configurer ensures role agent documentation instructs Goose agents never to access or mutate files outside the provisioned workspace root.

- The goose workspace configurer embeds command execution constraints in role agent documentation restricting shell usage strictly to the five prescribed workspace binaries.

- The goose workspace configurer returns a goose confinement report documenting all configured boundary files.
