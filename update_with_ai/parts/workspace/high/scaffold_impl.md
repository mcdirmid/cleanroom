# scaffold_impl implementation component

imports: session, cleanroom_files_ext, roles
implements: scaffold

## Purpose

The scaffold_impl implementation component realizes runner zipapp deployment, role descriptor metadata emission, AGENTS.md guide synthesis, and missing target starter skeleton generation.

Executing role workflows hermetically requires standalone runner tools embedded within `bin/` that forward invocation arguments to the Cleanroom role tool runtime while detecting the enclosing workspace and main repository root. Furthermore, agent guidance must explicitly convey the boundary rules, command restrictions, and fail-stop protocols required for safe autonomous operation. The scaffold_impl implementation component packages zipapp runners with execute permissions, writes role configuration into `.cleanroom_role.json`, formats comprehensive `AGENTS.md` instructions tailored to author or auditor roles, and synthesizes target skeletons using companion specifications.

**Out of scope:** The scaffold_impl implementation component does not create workspace directories, copy upstream contracts, or synchronize test stubs; these are handled by other components.

**Delegated:** Role definition resolution is delegated to roles or role_registry. File naming conventions for the role descriptor are delegated to cleanroom_files_ext.

## Types and Behavior

The workspace scaffolder prepares tooling, configuration, and instructions in role workspaces.

The workspace scaffolder:

- Deploys self-contained executable zipapps into the `bin/` directory of the workspace with execution permissions, packaging compiled Python bytecode (`.pyc`), source modules for cleanroom_role_tool, build_lint_common, and role verification linters, and the canonical role definitions configuration (`cleanroom_roles.toml`) inside the archive so that runners execute in-memory across Python runtime versions without exposing loose oracle files or configuration manifests in the role workspace filesystem, configuring runner import paths bounded strictly to the active role workspace root on sys.path without injecting arbitrary workspace subdirectories onto sys.path, isolating runner execution from the canonical repository root in sys.path, configuring runner namespace package bytecode with dynamic path extension for constituent parts directories, packaging blame and feedback runners only when the role declares feedback capability or auditor tags, and omitting them for author roles without feedback capability.

- Writes the role descriptor configuration file recording the role address, role name, and directory scope, omitting host repository paths to preserve isolation, with optional model profile attributes.

- Synthesizes an `AGENTS.md` guide containing the behavioral constraints, role instructions, and tool usage sequences tailored to the commissioned role, resolving companion guide paths both from the workspace root (e.g. `guides/<guide_name>.md`) and relative to the main repository.

- Writes boundary rules into the guide that confine the agent to the workspace, forbid git operations, declare the main repository read-only, explain that in-band metadata in role workspace files is projected to show only change, feedback, and ephemeral code hash fields while canonical lifecycle timestamps (such as last cleaned, last changed, and audit tags) are maintained exclusively in the main repository, and writes a contamination tripwire that mandates an immediate abort upon reading an out-of-bounds file outside the workspace directory, while explicitly permitting and instructing file inspection of in-workspace specifications, tests, code implementations, and commit change metadata headers, directing workers to rely on their assigned companion guide for module layout and conventions rather than searching for formatting reference files in the workspace.

- Writes execution guidance into the guide that permits shell commands and native harness tools within the workspace directory, while mandating that Cleanroom target verification and round resolution proceed through prescribed `bin/` executables (`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/fail`, and `bin/blame` only for roles declaring feedback capability), strictly enforcing continuous tool execution without conversational idling or dangling colons in model steps, ground-truth-first verification via `bin/check_files` before inspecting prose, targeted reads over full file dumps, prohibiting searching for internal linters or inspecting, decompiling, or reverse-engineering `bin/` executables, establishing a round conclusion protocol mandating that once all ready targets have been resolved or when get_work reports only blocked targets or zero ready targets, the worker must conclude the round immediately without further tool execution or conversational idling, and incorporating model-contingent payload ceiling protection directives instructing staged incremental writing when configured for local or output-constrained models while omitting them for cloud models.

- Writes a fail-stop and reporting protocol into the guide that prohibits self-healing on an infrastructure traceback, error, or missing dependency, while distinguishing ordinary verification test failures and establishing an unresolvable impasse protocol where failures are recorded via `bin/fail` and escalated to the coordinator.

- Writes instructions for acting on blame and feedback into the guide, warning authoring agents that static checks do not execute tests or verify runtime logic, clarifying that passing `bin/check_files` does not mean feedback is resolved, directing authors to resolve runtime defects in their assigned target files against contracts and tests before submitting, incorporating cleanroom compilation stub rules for roles declaring stub dependencies explaining that stub dependencies are read-only compilation stubs that must not be edited or asserted to raise stub errors, and mandating that auditor agents inspect target `# CHANGE:` commit headers before delivering blame to tailor feedback to what remains unaddressed without recycling identical critiques.

- Synthesizes starter skeleton files for declared writable target files that are absent from disk, inspecting companion specifications or templates resolved both from the workspace root (`./templates/<template_name>`) and relative to the main repository.

- Writes text files with explicit permissions (read-only, writable, or executable).

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-22T13:50:00Z
LAST_CHANGED: 2026-10-22T13:50:00Z
CHANGE: Enforce strict workspace root sys.path isolation in runner zipapps
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
