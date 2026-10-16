<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T18:50:00Z
CHANGE: Author workspace_scaffold_impl implementation specification
CODE_HASH: 07d173124131
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_scaffold_impl implementation component

imports: agent_session, cleanroom_files_ext, workspace_roles
implements: workspace_scaffold

## Purpose

The workspace_scaffold_impl implementation component realizes runner zipapp deployment, role descriptor metadata emission, AGENTS.md guide synthesis, and missing target starter skeleton generation.

Executing role workflows hermetically requires standalone runner tools embedded within `bin/` that forward invocation arguments to the Cleanroom role tool runtime while detecting the enclosing workspace and main repository root. Furthermore, agent guidance must explicitly convey the boundary rules, command restrictions, and fail-stop protocols required for safe autonomous operation. The workspace_scaffold_impl implementation component packages zipapp runners with execute permissions, writes role configuration into `.cleanroom_role.json`, formats comprehensive `AGENTS.md` instructions tailored to author or auditor roles, and synthesizes target skeletons using companion specifications.

**Out of scope:** The workspace_scaffold_impl implementation component does not create workspace directories, copy upstream contracts, or synchronize test stubs; these are handled by other components.

**Delegated:** Role definition resolution is delegated to workspace_roles or workspace_registry. File naming conventions for the role descriptor are delegated to cleanroom_files_ext.

## Types and Behavior

The workspace scaffolder prepares tooling, configuration, and instructions in role workspaces.

The workspace scaffolder:

- Deploys executable zipapp runner wrappers into the `bin/` directory of the workspace, packaging executable runners for the work, check files, submit, blame, fail, and coverage subcommands with execution permissions.

- Writes the role descriptor configuration file recording the role address, role name, and directory scope, omitting host repository paths to preserve isolation, with optional model profile attributes.

- Synthesizes an `AGENTS.md` guide containing the behavioral constraints, role instructions, and tool usage sequences tailored to the commissioned role.

- Writes boundary rules into the guide that confine the agent to the workspace, forbid git operations, and declare the main repository read-only, and writes a contamination tripwire that mandates an immediate abort upon reading an out-of-bounds file outside the workspace directory, while explicitly permitting and instructing file inspection of in-workspace specifications, tests, code implementations, and commit change metadata headers using file-reading tools.

- Writes a command execution tripwire into the guide that strictly restricts terminal shell command execution to prescribed `bin/` executables (`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, `bin/fail`) and mandates an immediate abort upon executing unapproved commands.

- Writes a fail-stop and reporting protocol into the guide that prohibits self-healing on an infrastructure traceback, error, or missing dependency, while distinguishing ordinary verification test failures and establishing an unresolvable impasse protocol where failures are recorded via `bin/fail` and escalated to the coordinator.

- Writes instructions for acting on blame and feedback into the guide, warning authoring agents that static checks do not execute tests or verify runtime logic, clarifying that passing `bin/check_files` does not mean feedback is resolved, directing authors to resolve runtime defects against contracts and tests before submitting, and mandating that auditor agents inspect target `# CHANGE:` commit headers before delivering blame to tailor feedback to what remains unaddressed without recycling identical critiques.

- Synthesizes starter skeleton files for declared writable target files that are absent from disk, inspecting companion specifications or templates.

- Writes text files with explicit permissions (read-only, writable, or executable).
