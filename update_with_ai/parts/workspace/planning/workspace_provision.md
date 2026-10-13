<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-11T03:16:22Z
CHANGE: Name the provisioner typing and contract workspace commissioning
CODE_HASH: 0a2f84ce71c6
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# workspace_provision interface component

## Intent

Uncontrolled read-write access across an entire codebase leads to accidental cross-tier modifications, out-of-scope code drift, and unintended edits to upstream contracts. Autonomous agents require hermetic environments where upstream contracts are strictly immutable, target files are explicitly bounded, and interaction is mediated through dedicated helper tools. The workspace_provision interface component establishes contracts for creating isolated role workspace trees, copying target and contract files with read-only permission enforcement (chmod 444), and deploying self-contained runner tools into bin/.

## Factored Contracts

### Typing

- An agent session's workspace provisioner creates and configures directory-scoped role workspaces.

### Contracts

- The workspace provisioner commissions an isolated role workspace for a specified role and directory scope, creating the workspace directory structure, configuring role metadata, and registering the workspace in the persistent registry. [commission_role_workspace]
- The workspace provisioner creates directory structures for commissioned role workspaces. [create_workspace_directories]
- The workspace provisioner copies writable target files into role workspaces with read-write permissions. [copy_writable_targets]
- The workspace provisioner copies upstream contract dependencies into role workspaces with read-only permissions. [copy_readonly_contracts]
- The workspace provisioner synthesizes read-only test stubs with NotImplementedError from companion specifications for stub role dependencies. [synthesize_readonly_test_stubs]
- The workspace provisioner packages executable runner tools into the workspace bin directory with execute permissions. [deploy_runner_executables]
- The workspace provisioner writes role configuration into cleanroom_files_ext.ROLE_DESCRIPTOR_FILE in the workspace root. [write_role_configuration]
- The workspace provisioner synthesizes role-tailored AGENTS.md instructions in the workspace root. [write_role_agents_instructions]

### Woven Contracts

- When commissioning a workspace, the provisioner resolves the role definition, creates directory structures, copies files with appropriate permissions, synthesizes stub dependencies, deploys runner tools, writes configuration, and registers the workspace. [create_workspace_directories, copy_writable_targets, copy_readonly_contracts, synthesize_readonly_test_stubs, deploy_runner_executables, write_role_configuration, write_role_agents_instructions, commission_role_workspace, workspace_registry: [resolve_role_definition, compute_workspace_directory_path, record_workspace_descriptor]]

## Grounding

### Knowledge Provisions

- Role workspace tree initialization, permission-isolated file copying, and executable runner deployment services. [workspace_provisioning_service]

### Knowledge Requirements

- Role descriptor file naming conventions.
  - Grounded: [cleanroom_files_ext: [cleanroom_files_schema]]
- Creation of directory structures and permission-enforced file copies on the filesystem.
  - Deferred: Provided by workspace provisioner implementation.
- Packaging and permission setting for runner executable zipapps.
  - Deferred: Provided by workspace provisioner implementation.
