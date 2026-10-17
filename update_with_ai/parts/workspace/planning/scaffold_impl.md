<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T18:50:00Z
CHANGE: Author scaffold_impl planning specification
CODE_HASH: 06debdc8c657
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# scaffold_impl implementation component

## Intent

Executing role workflows hermetically requires standalone runner tools embedded within bin/ that forward invocation arguments to the Cleanroom role tool runtime while detecting the enclosing workspace and main repository root. Furthermore, agent guidance must explicitly convey the boundary rules, command restrictions, and fail-stop protocols required for safe autonomous operation. The scaffold_impl implementation component packages zipapp runners with execute permissions, writes role configuration into .cleanroom_role.json, formats comprehensive AGENTS.md instructions tailored to author or auditor roles, and synthesizes target skeletons using companion specifications.

## Factored Contracts

### Contracts

- The workspace scaffolder creates executable zipapps containing __main__.py invoking cleanroom_role_tool. [package_runner_zipapps]
- The workspace scaffolder writes role metadata JSON containing role identity and directory scope to cleanroom_files_ext.ROLE_DESCRIPTOR_FILE without exposing host paths, supporting optional model execution profile settings. [serialize_role_descriptor]
- The workspace scaffolder formats AGENTS.md markdown with role constraints, strict boundary rules, a contamination tripwire (with permitted in-workspace code inspection), a terminal command execution restriction tripwire, instructions for acting on blame and feedback (including target change header inspection before auditor blame delivery), a fail-stop reporting protocol with unresolvable impasse handling via bin/fail, and tool execution instructions. [format_role_agents_markdown]
- The workspace scaffolder synthesizes starter skeleton files for declared writable target files that are absent from disk, inspecting companion specifications or templates. [synthesize_target_starter_skeletons]
- The workspace scaffolder applies explicit read-only, writable, or executable permissions when writing text files. [write_text_file_with_permissions]

### Woven Contracts

- When scaffolding a workspace, the scaffolder packages runner zipapps, serializes role metadata, formats AGENTS.md instructions, and generates target skeletons. [package_runner_zipapps, serialize_role_descriptor, format_role_agents_markdown, synthesize_target_starter_skeletons, write_text_file_with_permissions, scaffold: [deploy_runner_zipapps, write_role_metadata, write_role_agents_instructions, create_missing_target_skeletons, write_file_with_permissions]]

## Grounding

### Knowledge Provisions

- Standalone zipapp packaging, AGENTS.md synthesis, and starter skeleton generation mechanics. [workspace_scaffold_mechanics]

### Inherited Deferred Requirements

- Packaging and permission setting for runner executable zipapps.
  - Grounded: [workspace_scaffold_mechanics]
- Formatting and serialization of role metadata and AGENTS.md instructions.
  - Grounded: [workspace_scaffold_mechanics]

### Knowledge Requirements

- Role descriptor file naming conventions.
  - Grounded: [cleanroom_files_ext: [cleanroom_files_schema]]
- Role definition structure and metadata properties.
  - Grounded: [roles: [role_resolution_service]]
- Writing files and altering permissions on the local filesystem.
  - Grounded: [workspace_scaffold_mechanics]
