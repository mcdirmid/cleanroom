<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T18:50:00Z
CHANGE: Author workspace_scaffold planning specification
CODE_HASH: ed8935367a85
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_scaffold interface component

## Intent

Commissioned role workspaces require specialized executable tooling, in-band configuration, explicit agent operating instructions, and starter skeletons for new targets. Coupling this file synthesis and runner bundling directly into filesystem directory creation inflates workspace initialization logic and hinders isolated testing of agent guide formatting and tool packaging. The workspace_scaffold interface component establishes dedicated contracts for packaging standalone zipapp runners, writing role descriptor configuration without exposing host repository paths, formatting role-specific AGENTS.md documents with strict boundary tripwires and fail-stop protocols, and generating initial starter skeletons from companion specifications or templates.

## Factored Contracts

### Typing

- An agent session's workspace scaffolder prepares role runner tools, metadata configuration, role agent instructions, and target starter skeletons within commissioned role workspaces.

### Contracts

- The workspace scaffolder packages executable runner tools into the workspace bin directory with execute permissions. [deploy_runner_zipapps]
- The workspace scaffolder writes role configuration into cleanroom_files_ext.ROLE_DESCRIPTOR_FILE in the workspace root. [write_role_metadata]
- The workspace scaffolder synthesizes role-tailored AGENTS.md instructions in the workspace root. [write_role_agents_instructions]
- The workspace scaffolder synthesizes starter skeleton files for declared writable target files absent from disk. [create_missing_target_skeletons]
- The workspace scaffolder writes text files with explicit permissions. [write_file_with_permissions]

### Woven Contracts

- When scaffolding a role workspace, the scaffolder packages runner zipapps, writes role metadata, formats AGENTS.md instructions, and creates missing target skeletons. [deploy_runner_zipapps, write_role_metadata, write_role_agents_instructions, create_missing_target_skeletons, write_file_with_permissions]

## Grounding

### Knowledge Provisions

- Standalone runner tool packaging, role metadata serialization, agent guide synthesis, and missing target starter skeleton generation services. [workspace_scaffolding_service]

### Knowledge Requirements

- Role descriptor file naming conventions.
  - Grounded: [cleanroom_files_ext: [cleanroom_files_schema]]
- Role definition structure and metadata properties.
  - Grounded: [workspace_roles: [role_resolution_service]]
- Packaging and permission setting for runner executable zipapps.
  - Deferred: Provided by workspace scaffolder implementation.
- Formatting and serialization of role metadata and AGENTS.md instructions.
  - Deferred: Provided by workspace scaffolder implementation.
