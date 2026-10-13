<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_workspace_impl planning specification
CODE_HASH: 2d237e1db396
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# dsh_workspace_impl implementation component

## Intent

Provisioning physical Cleanroom role workspaces for DeepSeek Harness execution requires concrete filesystem instruction artifacts and overlay patches ensuring role confinement and non-interactive permission granting. Without reliable agent instruction configuration and overlay patches, DeepSeek Harness agents lack workspace-specific constraints upon startup and may violate Cleanroom isolation invariants or block on user confirmation prompts. The dsh_workspace_impl implementation component realizes the workspace configurer to safely configure DeepSeek Harness role directories.

## Factored Contracts

### Typing

- The dsh workspace configurer realization implements DshWorkspaceConfigurer and operates within the agent session tier.

### Contracts

- The realization incorporates explicit isolation boundaries, tripwires, and restricted binary directives tailored for DeepSeek Harness into role agent documentation within target role workspaces. [customize_role_agent_documentation]
- The realization generates a Cordis overlay patch file configuring danger-full-access permissions, approval policy never, and active model providers. [write_cordis_overlay_patch]
- The realization verifies that configured instruction files and patch files exist and are readable on disk. [verify_configured_files]
- The realization constructs a confinement report with directory path, role name, created file list, and success status. [construct_confinement_report]

### Woven Contracts

- When configuring workspaces, the realization customizes role agent documentation, writes overlay patches, and verifies file presence. [customize_role_agent_documentation, write_cordis_overlay_patch, verify_configured_files, dsh_workspace: [instruct_workspace_boundary, embed_command_constraints_in_docs, generate_cordis_overlay_patch]]
- When concluding configuration, the realization constructs and returns the confinement report. [construct_confinement_report, verify_configured_files, dsh_workspace: [return_confinement_report]]

## Grounding

### Knowledge Provisions

- DeepSeek Harness workspace boundary file customization, overlay patch synthesis, and verification mechanics. [dsh_workspace_mechanics]

### Inherited Deferred Requirements

- Role workspace instruction customization, overlay patch generation, and boundary verification logic.
  - Grounded: [dsh_workspace_mechanics]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [agent_session: [agent_session_tier_provision]]
