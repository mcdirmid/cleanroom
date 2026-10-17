<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_workspace interface specification
CODE_HASH: 402edcb4a5b0
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# dsh_workspace interface component

imports: session

## Purpose

The dsh_workspace interface component defines data types and operational contracts for configuring and confining isolated role workspaces for DeepSeek Harness through role instructions and Cordis overlay patches.

Autonomous agents operating inside role workspaces require explicit boundary guidance to prevent exploratory directory walking and cross-role file modifications. Without workspace-local instruction guidance and permission configuration, DeepSeek Harness agents may attempt unauthorized shell operations, halt for interactive approval, or inspect unblinded counterpart code. The dsh_workspace interface component formalizes boundary configuration, instruction tailoring within role agent documentation, Cordis overlay patch generation, and confinement reporting for DeepSeek Harness role workspaces.

**Out of scope:** The dsh_workspace interface component does not execute agent turns or evaluate DAG work queues; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *dsh confinement report* captures the isolation state of a role workspace, including the workspace directory, assigned role name, configured file sequence, and status indicator.

The *dsh workspace configurer* of an agent session customizes role workspace instructions, boundary constraints, and Cordis overlay patches for DeepSeek Harness.

When configuring a role workspace:

- The dsh workspace configurer ensures role agent documentation instructs DeepSeek Harness agents never to access or mutate files outside the provisioned workspace root.

- The dsh workspace configurer embeds command execution constraints in role agent documentation restricting shell usage strictly to the five prescribed workspace binaries.

- The dsh workspace configurer generates a targeted Cordis overlay patch file configuring model routing, resolving declared model configuration profiles against model configuration definitions discovered across workspace ancestors or repository root (stripping model prefixes), setting high reasoning effort for DeepSeek providers, disabling task management plugins, and unattended execution permissions.

- The dsh workspace configurer returns a dsh confinement report documenting all configured boundary files.
