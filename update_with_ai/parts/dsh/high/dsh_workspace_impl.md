<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_workspace_impl implementation specification
CODE_HASH: ee6cde1551b4
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# dsh_workspace_impl implementation component

imports: agent_session, dsh_ext
implements: dsh_workspace

## Purpose

The dsh_workspace_impl implementation component realizes workspace instruction customization and Cordis overlay patch generation for DeepSeek Harness role workspaces.

Provisioning physical Cleanroom role workspaces for DeepSeek Harness execution requires concrete filesystem instruction artifacts and overlay patches ensuring role confinement and non-interactive permission granting. Without reliable agent instruction configuration and overlay patches, DeepSeek Harness agents lack workspace-specific constraints upon startup and may violate Cleanroom isolation invariants or block on user confirmation prompts. The dsh_workspace_impl implementation component realizes the workspace configurer to safely configure DeepSeek Harness role directories.

**Out of scope:** The dsh_workspace_impl implementation component does not execute agent processes or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; platform format schemas are delegated to dsh_ext.

## Types and Behavior

The dsh workspace configurer customizes role agent documentation and generates overlay patch files within target role workspace directories.

When configuring role workspaces:

- The dsh workspace configurer incorporates explicit isolation boundaries, tripwires, and restricted binary directives tailored for DeepSeek Harness into role agent documentation.

- The dsh workspace configurer generates a Cordis patch file in `.cleanroom/dsh_patch.yml` configuring danger-full-access permissions, approval policy never, and requested model providers.

- The dsh workspace configurer verifies that configured instruction files and patch files exist and are readable on disk.

- The dsh workspace configurer returns a confinement report containing the workspace directory, assigned role name, list of created file paths, and successful configuration status.
