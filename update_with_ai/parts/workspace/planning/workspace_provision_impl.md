<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T17:45:00Z
CHANGE: align AGENTS.md planning with in-workspace file inspection and terminal command restrictions
CODE_HASH: ed27c745bdd4
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_provision_impl implementation component

## Intent

Provisioning isolated role workspaces requires precise file-level permission control to prevent agent hallucinations from overwriting immutable upstream contracts or deleting build rules. Incomplete workspace preparation or dangling file handles can cause agent sessions to fail on startup or corrupt subsequent runs. The workspace_provision_impl implementation component creates directory trees, selectively copies source files and build configurations, applies read-only attributes to upstream dependencies, embeds self-contained zipapp runner wrappers in bin/, and writes the role descriptor file designated by cleanroom_files_ext.

## Factored Contracts

### Contracts

- The workspace provisioner creates directory structures including bin and target package folders. [make_workspace_dirs]
- The workspace provisioner creates the role workspace working tree by copying workspace roots, project configurations, and build definitions while configuring type-checking to cover the workspace without directory exclusions. [create_workspace_working_tree]
- The workspace provisioner creates a missing target skeleton when a declared writable target file does not yet exist on disk. [create_missing_target_skeleton]
- The workspace provisioner copies files with permissions set to 0o644 for writable targets. [copy_file_with_write_perms]
- The workspace provisioner copies files with permissions set to 0o444 for read-only contracts. [copy_file_with_read_perms]
- The workspace provisioner applies explicit read-only, writable, or executable permissions when copying or writing files. [apply_file_permissions]
- The workspace provisioner synthesizes read-only test stubs with NotImplementedError from companion specifications for stub role dependencies. [synthesize_stub_role_dependencies]
- The workspace provisioner creates executable zipapps containing __main__.py invoking cleanroom_role_tool. [package_runner_zipapps]
- The workspace provisioner writes role metadata JSON containing role identity and directory scope to cleanroom_files_ext.ROLE_DESCRIPTOR_FILE without exposing host paths, supporting optional model execution profile settings. [serialize_role_descriptor]
- The workspace provisioner formats AGENTS.md markdown with role constraints, strict boundary rules, a contamination tripwire (with permitted in-workspace code inspection), a terminal command execution restriction tripwire, instructions for acting on blame and feedback (including target change header inspection before auditor blame delivery), a fail-stop reporting protocol with unresolvable impasse handling via bin/fail, and tool execution instructions. [format_role_agents_markdown]

### Woven Contracts

- When commissioning a workspace, the provisioner creates the working tree with type-checking coverage, creates missing target skeletons, creates folders, copies targets with write perms, copies contracts with read perms, applies file permissions, synthesizes stub role dependencies, packages runner zipapps, serializes role metadata, and writes AGENTS.md instructions. [make_workspace_dirs, create_workspace_working_tree, create_missing_target_skeleton, copy_file_with_write_perms, copy_file_with_read_perms, apply_file_permissions, synthesize_stub_role_dependencies, package_runner_zipapps, serialize_role_descriptor, format_role_agents_markdown, workspace_provision: [create_workspace_directories, copy_writable_targets, copy_readonly_contracts, copy_file_with_permissions, synthesize_readonly_test_stubs, deploy_runner_executables, write_role_configuration, write_role_agents_instructions], workspace_scaffold: [deploy_runner_zipapps, write_role_metadata, write_role_agents_instructions, create_missing_target_skeletons], workspace_stub: [generate_readonly_test_stub, sync_all_stub_deps, is_stub_dep_file]]


## Grounding

### Knowledge Provisions

- Filesystem permission setting and workspace provisioning mechanics. [workspace_filesystem_mechanics]

### Inherited Deferred Requirements

- Creation of directory structures and permission-enforced file copies on the filesystem.
  - Grounded: [workspace_filesystem_mechanics]
- Packaging and permission setting for runner executable zipapps.
  - Grounded: [workspace_scaffold: [workspace_scaffolding_service]]
- Runner zipapp deployment, role metadata serialization, and guide scaffolding services.
  - Grounded: [workspace_scaffold: [workspace_scaffolding_service]]

### Knowledge Requirements

- Role descriptor file naming conventions.
  - Grounded: [cleanroom_files_ext: [cleanroom_files_schema]]
- Writing files and altering permissions on the local filesystem.
  - Grounded: [workspace_filesystem_mechanics]
- Test stub generation, AST parsing, and dependency synchronization services.
  - Grounded: [workspace_stub: [workspace_stub_service]]
- Runner zipapp packaging, role metadata, and guide scaffolding services.
  - Grounded: [workspace_scaffold: [workspace_scaffolding_service]]
