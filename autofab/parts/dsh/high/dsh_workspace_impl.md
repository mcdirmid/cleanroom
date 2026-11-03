# dsh_workspace_impl implementation component

imports: session, dsh_ext
implements: dsh_workspace

## Purpose

The dsh_workspace_impl implementation component realizes workspace instruction customization and Cordis overlay patch generation for DeepSeek Harness role workspaces.

Provisioning physical Autofab role workspaces for DeepSeek Harness execution requires concrete filesystem instruction artifacts and overlay patches ensuring role confinement and non-interactive permission granting. Without reliable agent instruction configuration and overlay patches, DeepSeek Harness agents lack workspace-specific constraints upon startup and may violate Autofab isolation invariants or block on user confirmation prompts. The dsh_workspace_impl implementation component realizes the workspace configurer to safely configure DeepSeek Harness role directories.

**Out of scope:** The dsh_workspace_impl implementation component does not execute agent processes or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; platform format schemas are delegated to dsh_ext.

## Types and Behavior

The dsh workspace configurer customizes role agent documentation and generates overlay patch files within target role workspace directories.

When configuring role workspaces:

- The dsh workspace configurer incorporates explicit isolation boundaries, tripwires, permitted in-workspace read-only inspection shell utilities (`cat`, `grep`, `find`, `head`, `tail`, `sed`) and harness tool execution while strictly prohibiting ad-hoc runtime tests, test runners, or inline Python scripts (including `python3 -c` and stdin heredocs) against targets or implementation code, workspace undo and rollback instructions (`bin/revert [target]`, `git restore <target>`, `git diff <target>`) for authoring roles with writable targets, and auditor rules tailored for DeepSeek Harness into role agent documentation (strictly omitting rollback instructions, prohibiting code edits, and barring git commands for auditor roles), mandating in-workspace code and change header inspection while prohibiting code edits, mandating check_files as initial ground truth oracle, enforcing continuous tool execution while work remains without conversational halts or dangling colons, requiring round resolution via submit or fail (and blame only for roles declaring feedback capability or auditor tags), and mandating that when the worker has no outstanding work to do and get_work gives no more work to do (all ready targets have been resolved or only blocked targets remain), the worker can and must conclude the round immediately by delivering its text summary without further tool calls.

- When configuring role workspaces for local or output-constrained models (such as local MLX, oMLX, or models with low output ceilings), the dsh workspace configurer embeds payload ceiling and incremental staged writing directives into role agent documentation to prevent mid-turn tool envelope truncation, omitting this guidance when targeting cloud models with large output capacities.

- The dsh workspace configurer generates a Cordis patch file in `.autofab/dsh_patch.yml` configuring danger-full-access permissions for authoring roles (or read-only sandbox mode disabling edit and write tools for auditor roles with zero writable targets), approval policy never, high reasoning effort for DeepSeek providers, pre-tool lifecycle hooks on edit and write tools that trigger `bin/checkpoint pre-edit` for authoring roles (omitting pre-tool checkpoint hooks for auditor roles), disabling unneeded tool plugins (including workflow, subagent, office skills, web, user question, jobs, and goal tools) to eliminate prompt overhead, and requested model providers, resolving declarative model profile names (stripping model namespace prefixes) against model configuration definitions discovered in workspace ancestors, working directories, user configuration, or repository hierarchy, mapping local MLX providers to oMLX endpoints.

- The dsh workspace configurer verifies that configured instruction files and patch files exist and are readable on disk.

- The dsh workspace configurer returns a confinement report containing the workspace directory, assigned role name, list of created file paths, and successful configuration status.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-20T22:50:00Z
LAST_CHANGED: 2026-11-02T20:38:00Z
CHANGE: Prohibit ad-hoc runtime testing and inline python scripts in customized AGENTS.md
SPEC_QA_AUDIT: 2026-10-19T22:33:00Z
-->
