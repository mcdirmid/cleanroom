<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: 1ec0e24bed0f
-->

# workspace_provision interface component

imports: agent_session, workspace_registry

## Intent

Uncontrolled read-write access across an entire codebase leads to accidental cross-tier modifications, out-of-scope code drift, and unintended edits to upstream contracts. Autonomous agents require hermetic environments where upstream contracts are strictly immutable, target files are explicitly bounded, and interaction is mediated through dedicated helper tools. The workspace_provision interface component establishes contracts for creating isolated role workspace trees, copying target and contract files with read-only permission enforcement (chmod 444), deploying self-contained runner tools into bin/, and removing clean workspaces upon decommissioning.

## Factored Contracts

### Typing

- A workspace provisioner operates within the agent session lifecycle tier.

### Contracts

- The workspace provisioner creates directory structures for commissioned role workspaces. [create_workspace_directories]
- The workspace provisioner copies writable target files into role workspaces with read-write permissions. [copy_writable_targets]
- The workspace provisioner copies upstream contract dependencies into role workspaces with read-only permissions. [copy_readonly_contracts]
- The workspace provisioner packages executable runner tools into the workspace bin directory with execute permissions. [deploy_runner_executables]
- The workspace provisioner writes role configuration into .cleanroom_role.json in the workspace root. [write_role_configuration]
- The workspace provisioner synthesizes role-tailored AGENTS.md instructions in the workspace root. [write_role_agents_instructions]
- The workspace provisioner verifies whether unharvested modifications exist in the workspace before decommissioning. [verify_clean_before_decommission]
- The workspace provisioner removes the role workspace directory tree upon decommissioning. [delete_workspace_directory_tree]

### Woven Contracts

- When commissioning a workspace, the provisioner resolves the role definition, creates directory structures, copies files with appropriate permissions, deploys runner tools, writes configuration, and registers the workspace. [create_workspace_directories, copy_writable_targets, copy_readonly_contracts, deploy_runner_executables, write_role_configuration, write_role_agents_instructions, workspace_registry: [resolve_standard_role_definition, compute_workspace_directory_path, record_workspace_descriptor]]
- When decommissioning a workspace, the provisioner verifies that no unharvested modifications remain, unregisters the workspace descriptor, and deletes the workspace directory tree. [verify_clean_before_decommission, delete_workspace_directory_tree, workspace_registry: [unregister_workspace_descriptor]]

## Grounding

### Knowledge Provisions

- Role workspace tree initialization, permission-isolated file copying, and executable runner deployment services. [workspace_provisioning_service]
- Safe workspace verification and recursive decommissioning mechanics. [workspace_decommissioning_service]

### Knowledge Requirements

- Creation of directory structures and permission-enforced file copies on the filesystem.
  - Deferred: Provided by workspace provisioner implementation.
- Packaging and permission setting for runner executable zipapps.
  - Deferred: Provided by workspace provisioner implementation.
- Verification of uncommitted file modifications and recursive deletion on disk.
  - Deferred: Provided by workspace provisioner implementation.
