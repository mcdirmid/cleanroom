<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T09:50:00Z
CHANGE: author goose_workspace_impl implementation specification
CODE_HASH: 57b0c1898761
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# goose_workspace_impl implementation component

imports: agent_session, goose_ext
implements: goose_workspace

## Purpose

The goose_workspace_impl implementation component realizes workspace instruction customization for Goose role workspaces.

Provisioning physical Cleanroom role workspaces for Goose execution requires concrete filesystem instruction artifacts ensuring role confinement. Without reliable agent instruction configuration, Goose agents lack workspace-specific constraints upon startup and may violate Cleanroom isolation invariants. The goose_workspace_impl implementation component realizes the workspace configurer to safely configure Goose role directories.

**Out of scope:** The goose_workspace_impl implementation component does not execute agent processes or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; platform format schemas are delegated to goose_ext.

## Types and Behavior

The goose workspace configurer customizes role agent documentation within target role workspace directories.

When configuring role workspaces:

- The goose workspace configurer incorporates explicit isolation boundaries, tripwires, and restricted binary directives tailored for Goose into role agent documentation.

- The goose workspace configurer verifies that configured instruction files exist and are readable on disk.

- The goose workspace configurer returns a confinement report containing the workspace directory, assigned role name, list of created file paths, and successful configuration status.
