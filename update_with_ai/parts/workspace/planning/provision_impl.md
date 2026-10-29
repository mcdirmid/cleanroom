# provision_impl implementation component

## Intent

Provisioning isolated role workspaces requires precise file-level permission control to prevent agent hallucinations from overwriting immutable upstream contracts or deleting build rules. Incomplete workspace preparation or dangling file handles can cause agent sessions to fail on startup or corrupt subsequent runs. The provision_impl implementation component creates directory trees, selectively copies source files and build configurations, applies read-only attributes to upstream dependencies, embeds self-contained zipapp runner wrappers in bin/, and writes the role descriptor file designated by cleanroom_files_ext.

## Factored Contracts

### Contracts

- The workspace provisioner creates directory structures including bin and target package folders. [make_workspace_dirs]
- The workspace provisioner creates the role workspace working tree by copying workspace roots, project configurations, and build definitions, resolving the target scope's bound methodology package from cleanroom.toml, and projecting active methodology runtime support libraries directly to ./support/lib and assigned companion guides to ./guides (copying all companion guides across constituent roles for fused roles), while strictly avoiding copying templates, unneeded configuration files, or unbound repository root directories and configuring type-checking to cover the workspace without directory exclusions. [create_workspace_working_tree]
- The workspace provisioner creates a missing target skeleton when a declared writable target file does not yet exist on disk. [create_missing_target_skeleton]
- The workspace provisioner copies files with permissions set to 0o644 for writable targets, projecting in-band metadata to expose only change, feedback, and ephemeral code hash attributes. [copy_file_with_write_perms]
- The workspace provisioner copies files with permissions set to 0o444 for read-only contracts, copying runtime libraries into root support directories while strictly excluding internal methodology oracles, AST linters, and role runners. [copy_file_with_read_perms]
- The workspace provisioner applies explicit read-only, writable, or executable permissions when copying or writing files. [apply_file_permissions]
- The workspace provisioner synthesizes read-only test stubs with NotImplementedError from companion specifications for stub role dependencies. [synthesize_stub_role_dependencies]
- The workspace provisioner creates self-contained executable zipapps containing compiled .pyc bytecode and source modules for cleanroom_role_tool, build_lint_common, and role verification linters, including use-based micro-binaries for fused roles. [package_runner_zipapps]
- The workspace provisioner writes role metadata JSON containing role identity and directory scope to cleanroom_files_ext.ROLE_DESCRIPTOR_FILE without exposing host paths, supporting optional model execution profile settings. [serialize_role_descriptor]
- The workspace provisioner formats AGENTS.md markdown with role constraints, strict boundary rules, a contamination tripwire for out-of-bounds files, permitted in-workspace shell and harness tool execution, instructions for acting on blame and feedback (including target change header inspection before auditor blame delivery), a fail-stop reporting protocol with unresolvable impasse handling via bin/fail, and mandatory round resolution instructions. [format_role_agents_markdown]

### Woven Contracts

- When commissioning a workspace, the provisioner creates the working tree with type-checking coverage, creates missing target skeletons, creates folders, copies targets with write perms, copies contracts with read perms, applies file permissions, synthesizes stub role dependencies, packages runner zipapps, serializes role metadata, and writes AGENTS.md instructions. [make_workspace_dirs, create_workspace_working_tree, create_missing_target_skeleton, copy_file_with_write_perms, copy_file_with_read_perms, apply_file_permissions, synthesize_stub_role_dependencies, package_runner_zipapps, serialize_role_descriptor, format_role_agents_markdown, provision: [create_workspace_directories, copy_writable_targets, copy_readonly_contracts, copy_file_with_permissions, synthesize_readonly_test_stubs, deploy_runner_executables, write_role_configuration, write_role_agents_instructions], scaffold: [deploy_runner_zipapps, write_role_metadata, write_role_agents_instructions, create_missing_target_skeletons], stub: [generate_readonly_test_stub, sync_all_stub_deps, is_stub_dep_file], src_metadata: [extract_metadata_disk, update_metadata_disk]]


## Grounding

### Knowledge Provisions

- Filesystem permission setting and workspace provisioning mechanics. [workspace_filesystem_mechanics]

### Inherited Deferred Requirements

- Creation of directory structures and permission-enforced file copies on the filesystem.
  - Grounded: [workspace_filesystem_mechanics]
- Packaging and permission setting for runner executable zipapps.
  - Grounded: [scaffold: [workspace_scaffolding_service]]
- Runner zipapp deployment, role metadata serialization, and guide scaffolding services.
  - Grounded: [scaffold: [workspace_scaffolding_service]]

### Knowledge Requirements

- Role descriptor file naming conventions.
  - Grounded: [cleanroom_files_ext: [cleanroom_files_schema]]
- Writing files and altering permissions on the local filesystem.
  - Grounded: [workspace_filesystem_mechanics]
- Test stub generation, AST parsing, and dependency synchronization services.
  - Grounded: [stub: [workspace_stub_service]]
- Runner zipapp packaging, role metadata, and guide scaffolding services.
  - Grounded: [scaffold: [workspace_scaffolding_service]]
- In-band metadata extraction, projection, and ephemeral code hash generation.
  - Grounded: [src_metadata: [source_metadata_service]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T20:38:00Z
LAST_CHANGED: 2026-10-26T20:38:00Z
CHANGE: Provision all companion guides and use-based micro-binaries for fused roles
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
