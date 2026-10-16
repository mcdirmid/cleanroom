<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_workspace planning specification
CODE_HASH: 99460640d1c9
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# dsh_workspace interface component

## Intent

Autonomous agents operating inside role workspaces require explicit boundary guidance to prevent exploratory directory walking and cross-role file modifications. Without workspace-local instruction guidance and permission configuration, DeepSeek Harness agents may attempt unauthorized shell operations, halt for interactive approval, or inspect unblinded counterpart code. The dsh_workspace interface component formalizes boundary configuration, instruction tailoring within role agent documentation, Cordis overlay patch generation, and confinement reporting for DeepSeek Harness role workspaces.

## Factored Contracts

### Typing

- A dsh confinement report holds workspace directory, role name, configured files, and status indicator.
- A dsh workspace configurer operates in the agent session tier and customizes role workspace instructions, boundary constraints, and Cordis overlay patches for DeepSeek Harness.

### Contracts

- A dsh workspace configurer ensures role agent documentation instructs DeepSeek Harness agents never to access or mutate files outside the provisioned workspace root. [instruct_workspace_boundary]
- A dsh workspace configurer embeds command execution constraints in role agent documentation restricting shell usage strictly to the five prescribed workspace binaries. [embed_command_constraints_in_docs]
- A dsh workspace configurer generates a targeted Cordis overlay patch file configuring model routing, resolving declared model configuration profiles to their underlying model identifiers, and unattended execution permissions. [generate_cordis_overlay_patch]
- A dsh workspace configurer returns a dsh confinement report documenting all configured boundary files. [return_confinement_report]

### Woven Contracts

- When configuring a role workspace, the configurer customizes role agent documentation with boundary instructions and command execution constraints and generates an overlay patch. [instruct_workspace_boundary, embed_command_constraints_in_docs, generate_cordis_overlay_patch]
- Upon finishing workspace configuration, the configurer returns a confinement report documenting all configured boundary files. [return_confinement_report, instruct_workspace_boundary, embed_command_constraints_in_docs, generate_cordis_overlay_patch]

## Grounding

### Knowledge Provisions

- DeepSeek Harness workspace configuration, isolation boundary, and overlay patch services. [dsh_workspace_services]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [agent_session: [agent_session_tier_provision]]
- Role workspace instruction customization, overlay patch generation, and boundary verification logic.
  - Deferred: Realized by the dsh workspace implementation component.
