# scaffold_impl implementation component

## Intent

Executing role workflows hermetically requires standalone runner tools embedded within bin/ that forward invocation arguments to the Autofab role tool runtime while detecting the enclosing workspace and main repository root. Furthermore, agent guidance must explicitly convey workspace boundary rules, permitted in-workspace shell execution, and fail-stop protocols required for safe autonomous operation. The scaffold_impl implementation component packages zipapp runners with execute permissions, writes role configuration into .autofab_role.json, formats comprehensive AGENTS.md instructions tailored to author or auditor roles, and synthesizes target skeletons using companion specifications.

## Factored Contracts

### Contracts

- The workspace scaffolder creates self-contained executable zipapps containing compiled .pyc bytecode for autofab_role_tool, build_lint_common, and role verification linters, and the canonical role definitions manifest (autofab_roles.toml), configuring runner import paths bounded strictly to the active role workspace root on sys.path without injecting arbitrary workspace subdirectories onto sys.path, isolating runner execution from the canonical repository root in sys.path, configuring runner execution environments with UV_PROJECT bound to the discovered main repository root for subprocess execution, packaging blame only when the role declares feedback capability or auditor tags, omitting blame for author roles without feedback capability, deploying rollback and checkpoint runners (revert, checkpoint) for authoring roles with writable targets (omitting revert and checkpoint for auditor roles with zero writable targets), and deploying use-based micro-binaries (verify_<constituent_role> for each constituent role declared in the fused role definition) for fused roles. [package_runner_zipapps]
- The workspace scaffolder writes role metadata JSON containing role identity, directory scope, and common specification roles to autofab_files_ext.ROLE_DESCRIPTOR_FILE without exposing host paths, supporting optional model execution profile settings, and recording constituent role names for fused roles. [serialize_role_descriptor]
- The workspace scaffolder formats AGENTS.md markdown with role constraints, strict boundary rules prohibiting root filesystem traversal or scanning parent directories and explaining that in-band metadata in role workspaces is projected to show change, feedback, and code hash fields while canonical lifecycle timestamps are maintained in the main repository, a contamination tripwire for out-of-bounds files, establishing that for auditor roles bin/get_work serves as the primary verification and auto-submission mechanism, permitted in-workspace read-only inspection shell utilities (cat, grep, find, head, tail, sed) and harness tool execution while strictly prohibiting ad-hoc runtime tests, test runners, or inline Python scripts (including python3 -c and stdin heredocs) against targets or implementation code, while for authoring roles with writable targets instructing local git rollback and inspection commands (git restore, git diff, bin/revert) to recover from broken edits without calling bin/fail and for auditor roles with zero writable targets omitting undo guidance and strictly prohibiting file edits and git commands, instructions for acting on blame and feedback (including target change header inspection and autofab triage summaries before auditor blame delivery without authoring debug scripts, an immediate post-blame post-completion protocol instructing that once blame or submit has been delivered, the worker must run bin/get_work to verify remaining units and, if all ready work is resolved, conclude the round immediately with summary text and zero further tool calls without re-running verification or debugging author code, grounding sole-custodian file ownership explaining that downstream roles deliver feedback via bin/get_work and appended metadata while no external process mutates author code, dynamic target references without hardcoded library files, autofab compilation stub rules for roles declaring stub dependencies, and omission of blame directives for roles without feedback capability), a fail-stop reporting protocol (distinguishing normal test failures, timeouts, hangs, and SIGTERM as code defects rather than infrastructure crashes) with unresolvable impasse handling via bin/fail, prohibitions against linter hunting and runner binary inspection, reliance on companion guides (resolving guide paths from workspace root and repository root) for reference format, mandatory round resolution instructions, an explicit round conclusion protocol directing the worker that once it has no outstanding work to do and get_work gives no more work to do (all ready targets have been resolved or only blocked targets remain), it can and must conclude the round immediately by outputting its final summary text without executing further tool calls, enforcing targeted chunk reads over sequential micro-reading loops, model-contingent payload ceiling protection directives instructing staged incremental writing when configured for local or output-constrained models while omitting them for cloud models, and tailored multi-phase instructions for fused roles dynamically derived from constituent role definitions and metadata (partitioning targets into upstream contract sources, implementation targets, and verification test targets without hardcoded role or file names), incorporating contract grounding, test authoring embedding operational postconditions into transition ctx.ensures(...) handlers and driving scenarios via transition dispatch without redundant manual assertions while forbidding assertions on uncontracted non-concerns or synthetic graph placeholders, implementation realization, and verification with targeted reads, use-based micro-binary verification for each constituent role (executing full test suites including property fuzz testing during QA self-audit while reserving coverage flags exclusively for coverage verification), QA arbiter contract fidelity and type contract respect audits, coverage arbiter semantic closure audits requiring pruning uncontracted dead defensive code upon coverage failures, and completion notifications without per-target submissions. [format_role_agents_markdown]
- The workspace scaffolder synthesizes starter skeleton files for declared writable target files that are absent from disk, executing the role's declared template command within the repository project environment with UV_PROJECT configured when configured, or falling back to inspecting companion specifications or templates resolved both from the workspace root and main repository, with zero hardcoded file patterns or tool imports. [synthesize_target_starter_skeletons]
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
  - Grounded: [autofab_files_ext: [autofab_files_schema]]
- Role definition structure and metadata properties.
  - Grounded: [roles: [role_resolution_service]]
- Writing files and altering permissions on the local filesystem.
  - Grounded: [workspace_scaffold_mechanics]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T11:00:00Z
LAST_CHANGED: 2026-11-03T20:40:00Z
CHANGE: Ground template command execution in repository environment with UV_PROJECT and bind UV_PROJECT in runner zipapps
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
