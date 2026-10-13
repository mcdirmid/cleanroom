<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T11:20:00Z
CHANGE: align with HLS role agent documentation customization
CODE_HASH: 9c0d7f2cbe2a
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# goose_workspace interface component

## Intent

Autonomous agents operating inside role workspaces require explicit boundary guidance to prevent exploratory directory walking and cross-role file modifications. Without workspace-local instruction guidance, Goose agents may attempt unauthorized shell operations or inspect unblinded counterpart code. The goose_workspace interface component formalizes boundary configuration, instruction tailoring within role agent documentation, and confinement reporting for Goose role workspaces.

## Factored Contracts

### Typing

- A goose confinement report holds workspace directory, role name, configured files, and status indicator.
- A goose workspace configurer operates in the agent session tier and customizes role workspace instructions and boundary constraints for Goose.

### Contracts

- A goose workspace configurer ensures role agent documentation instructs Goose agents never to access or mutate files outside the provisioned workspace root. [instruct_workspace_boundary]
- A goose workspace configurer embeds command execution constraints in role agent documentation restricting shell usage strictly to the five prescribed workspace binaries. [embed_command_constraints_in_docs]
- A goose workspace configurer returns a goose confinement report documenting all configured boundary files. [return_confinement_report]

### Woven Contracts

- When configuring a role workspace, the configurer customizes role agent documentation with boundary instructions and command execution constraints. [instruct_workspace_boundary, embed_command_constraints_in_docs]
- Upon finishing workspace configuration, the configurer returns a confinement report documenting all configured boundary files. [return_confinement_report, instruct_workspace_boundary, embed_command_constraints_in_docs]

## Grounding

### Knowledge Provisions

- Goose workspace configuration and isolation boundary services. [goose_workspace_services]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [agent_session: [agent_session_tier_provision]]
- Role workspace instruction customization and boundary verification logic.
  - Deferred: Realized by the goose workspace implementation component.
