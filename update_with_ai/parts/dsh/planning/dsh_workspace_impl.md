<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:45:00Z
CHANGE: align dsh_workspace_impl planning with auditor code inspection and terminal command restrictions
CODE_HASH: 9e4d2523bf6e
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# dsh_workspace_impl implementation component

## Intent

Provisioning physical Cleanroom role workspaces for DeepSeek Harness execution requires concrete filesystem instruction artifacts and overlay patches ensuring role confinement and non-interactive permission granting. Without reliable agent instruction configuration and overlay patches, DeepSeek Harness agents lack workspace-specific constraints upon startup and may violate Cleanroom isolation invariants or block on user confirmation prompts. The dsh_workspace_impl implementation component realizes the workspace configurer to safely configure DeepSeek Harness role directories.

## Factored Contracts

### Typing

- The dsh workspace configurer realization implements DshWorkspaceConfigurer and operates within the agent session tier.

### Contracts

- The realization incorporates explicit isolation boundaries, tripwires, restricted binary directives, and auditor rules into role agent documentation within target role workspaces, mandating in-workspace code and change header inspection while prohibiting code edits. [customize_role_agent_documentation]
- The realization generates a Cordis overlay patch file configuring danger-full-access permissions, approval policy never, high reasoning effort for DeepSeek providers, disabled task management plugins, and active model providers, resolving declarative model profile names (stripping model namespace prefixes) against model configuration definitions discovered in workspace ancestors, working directories, or repository hierarchy. [write_cordis_overlay_patch]
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
  - Grounded: [session: [agent_session_tier_provision]]
