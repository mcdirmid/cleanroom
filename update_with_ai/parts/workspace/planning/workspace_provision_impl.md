<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-09T02:39:58Z
CHANGE: add contamination tripwire to format_role_agents_markdown contract
CODE_HASH: 80392d8650d6
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# workspace_provision_impl implementation component

imports: agent_session, workspace_registry
implements: workspace_provision

## Intent

Provisioning isolated role workspaces requires precise file-level permission control to prevent agent hallucinations from overwriting immutable upstream contracts or deleting build rules. Incomplete workspace preparation or dangling file handles can cause agent sessions to fail on startup or corrupt subsequent runs. The workspace_provision_impl implementation component creates directory trees, selectively copies source files and build configurations, applies read-only attributes to upstream dependencies, embeds self-contained zipapp runner wrappers in bin/, and writes .cleanroom_role.json.

## Factored Contracts

### Contracts

- The workspace provisioner creates directory structures including bin and target package folders. [make_workspace_dirs]
- The workspace provisioner copies files with permissions set to 0o644 for writable targets. [copy_file_with_write_perms]
- The workspace provisioner copies files with permissions set to 0o444 for read-only contracts. [copy_file_with_read_perms]
- The workspace provisioner synthesizes read-only test stubs with NotImplementedError from companion specifications for stub role dependencies. [synthesize_stub_role_dependencies]
- The workspace provisioner creates executable zipapps containing __main__.py invoking cleanroom_role_tool. [package_runner_zipapps]
- The workspace provisioner writes role metadata JSON containing main root and directory scope to .cleanroom_role.json. [serialize_role_descriptor]
- The workspace provisioner formats AGENTS.md markdown with role constraints, strict boundary rules, a contamination tripwire, a fail-stop reporting protocol, and tool execution instructions. [format_role_agents_markdown]

### Woven Contracts

- When commissioning a workspace, the provisioner creates folders, copies targets with write perms, copies contracts with read perms, synthesizes stub role dependencies, packages runner zipapps, serializes role metadata, and writes AGENTS.md instructions. [make_workspace_dirs, copy_file_with_write_perms, copy_file_with_read_perms, synthesize_stub_role_dependencies, package_runner_zipapps, serialize_role_descriptor, format_role_agents_markdown, workspace_provision: [create_workspace_directories, copy_writable_targets, copy_readonly_contracts, synthesize_readonly_test_stubs, deploy_runner_executables, write_role_configuration, write_role_agents_instructions]]

## Grounding

### Knowledge Provisions

- Filesystem permission setting and zipapp packaging mechanics. [workspace_filesystem_mechanics]

### Inherited Deferred Requirements

- Creation of directory structures and permission-enforced file copies on the filesystem.
  - Grounded: [workspace_filesystem_mechanics]
- Packaging and permission setting for runner executable zipapps.
  - Grounded: [workspace_filesystem_mechanics]

### Knowledge Requirements

- Writing files and altering permissions on the local filesystem.
  - Grounded: [workspace_filesystem_mechanics]
