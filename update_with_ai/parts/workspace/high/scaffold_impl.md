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

- Deploys self-contained executable zipapps into the `bin/` directory of the workspace with execution permissions, packaging compiled Python bytecode (`.pyc`), source modules for cleanroom_role_tool, build_lint_common, and role verification linters, and the canonical role definitions configuration (`cleanroom_roles.toml`) inside the archive so that runners execute in-memory across Python runtime versions without exposing loose oracle files or configuration manifests in the role workspace filesystem, configuring runner import paths bounded strictly to the active role workspace root on sys.path without injecting arbitrary workspace subdirectories onto sys.path, isolating runner execution from the canonical repository root in sys.path, configuring runner namespace package bytecode with dynamic path extension for constituent parts directories, packaging blame and feedback runners only when the role declares feedback capability or auditor tags, omitting them for author roles without feedback capability, and deploying use-based micro-binaries (`bin/verify_<role>` for each constituent role declared in the fused role definition, such as `bin/verify_lib`, `bin/verify_test`, `bin/verify_qa`, `bin/verify_pretense`, `bin/verify_pretense_qa`, `bin/verify_coverage`) for fused roles to enable hermetic target verification without host repository references.

- Writes the role descriptor configuration file recording the role address, role name, directory scope, and common specification roles, omitting host repository paths to preserve isolation, with optional model profile attributes.

- Synthesizes an `AGENTS.md` guide containing the behavioral constraints, role instructions, and tool usage sequences tailored to the commissioned role, resolving companion guide paths both from the workspace root (e.g. `guides/<guide_name>.md`) and relative to the main repository, and when commissioning a fused role, dynamically deriving instructions from constituent role definitions and metadata (partitioning targets into upstream contract sources, implementation targets, and verification test targets without hardcoded role or file names), generating multi-phase instructions (contract grounding, test authoring embedding operational postconditions into transition `ctx.ensures(...)` handlers and driving scenarios via transition dispatch without redundant manual assertions while forbidding assertions on uncontracted non-concerns or synthetic graph placeholders, implementation realization, and verification with targeted reads) incorporating use-based micro-binary verification for each constituent role (executing full test suites including property fuzz testing during QA self-audit while reserving coverage flags exclusively for coverage verification), QA arbiter self-audit directives against contract fidelity and type contract respect (forbidding passing None or invalid types into strictly-typed non-optional parameters), coverage arbiter semantic closure directives requiring pruning uncontracted dead defensive code, and an atomic completion protocol omitting per-target submission.

- Writes boundary rules into the guide that confine the agent to the workspace, forbid git operations, declare the main repository read-only, explain that in-band metadata in role workspace files is projected to show only change, feedback, and ephemeral code hash fields while canonical lifecycle timestamps (such as last cleaned, last changed, and audit tags) are maintained exclusively in the main repository, and writes a contamination tripwire that mandates an immediate abort upon reading an out-of-bounds file outside the workspace directory, while explicitly permitting and instructing file inspection of in-workspace specifications, tests, code implementations, and commit change metadata headers, directing workers to rely on their assigned companion guide for module layout and conventions rather than searching for formatting reference files in the workspace.

- Writes execution guidance into the guide that permits shell commands and native harness tools within the workspace directory, while mandating that Cleanroom target verification and round resolution proceed through prescribed `bin/` executables (`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/fail`, and `bin/blame` only for roles declaring feedback capability), strictly enforcing continuous tool execution while work remains without conversational idling or dangling colons in model steps, ground-truth-first verification via `bin/check_files` before inspecting prose, targeted reads over full file dumps, prohibiting searching for internal linters or inspecting, decompiling, or reverse-engineering `bin/` executables, establishing a round conclusion protocol instructing that once the worker has no outstanding work to do and get_work gives no more work to do (all ready targets have been resolved or only blocked targets remain), the worker can and must conclude the round immediately by outputting its final summary text without executing further tool calls, and incorporating model-contingent payload ceiling protection directives instructing staged incremental writing when configured for local or output-constrained models while omitting them for cloud models.

- Writes a fail-stop and reporting protocol into the guide that prohibits self-healing on an infrastructure traceback, error, or missing dependency, while distinguishing ordinary verification test failures (and explicitly clarifying that execution timeouts, process hangs, and termination by SIGTERM during test verification are code defects such as infinite loops, deadlocks, or live-locks rather than infrastructure failures) and establishing an unresolvable impasse protocol where failures are recorded via `bin/fail` and escalated to the coordinator.

- Writes instructions for acting on blame and feedback into the guide, warning authoring agents that static checks do not execute tests or verify runtime logic, clarifying that passing `bin/check_files` does not mean feedback is resolved, directing authors to resolve runtime defects in their assigned target files against contracts and tests before submitting, incorporating cleanroom compilation stub rules for roles declaring stub dependencies explaining that stub dependencies are read-only compilation stubs that must not be edited or asserted to raise stub errors, and mandating that auditor agents inspect target `# CHANGE:` commit headers before delivering blame to tailor feedback to what remains unaddressed without recycling identical critiques.

- Synthesizes starter skeleton files for declared writable target files that are absent from disk, inspecting companion specifications or templates resolved both from the workspace root (`./templates/<template_name>`) and relative to the main repository.

- Writes text files with explicit permissions (read-only, writable, or executable).

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-27T11:35:00Z
LAST_CHANGED: 2026-10-29T15:30:00Z
CHANGE: Derive fused role micro-binaries strictly and dynamically from constituent role names with zero hardcoded role names
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
