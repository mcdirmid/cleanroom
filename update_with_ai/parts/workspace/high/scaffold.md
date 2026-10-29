# scaffold interface component

imports: session, cleanroom_files_ext, roles

## Purpose

The scaffold interface component defines operational contracts for deploying runner zipapps, serializing role metadata, synthesizing role-tailored AGENTS.md guide instructions, and generating missing target skeletons within Cleanroom role workspaces.

Commissioned role workspaces require specialized executable tooling, in-band configuration, explicit agent operating instructions, and starter skeletons for new targets. Coupling this file synthesis and runner bundling directly into filesystem directory creation inflates workspace initialization logic and hinders isolated testing of agent guide formatting and tool packaging. The scaffold interface component establishes dedicated contracts for packaging standalone zipapp runners, writing role descriptor configuration without exposing host repository paths, formatting role-specific AGENTS.md documents with strict boundary tripwires and fail-stop protocols, and generating initial starter skeletons from companion specifications or templates.

**Out of scope:** The scaffold interface component does not create top-level workspace directory trees, resolve workspace paths, or synchronize implementation files; these are handled by other components.

**Delegated:** Role metadata resolution and role definitions are delegated to roles or role_registry. File naming conventions for the role descriptor configuration are delegated to cleanroom_files_ext.

## Types and Behavior

An agent session's *workspace scaffolder* prepares role runner tools, metadata configuration, role agent instructions, and target starter skeletons within commissioned role workspaces.

The workspace scaffolder:

- Deploys executable runner tools into the `bin/` directory of the workspace, packaging work, check files, submit, and fail runners as standalone zipapp executables with execution permissions, packaging blame only when the role declares feedback capability or auditor tags, and omitting blame for author roles without feedback capability.

- Writes workspace role configuration into a hidden role descriptor file recording role identity, directory scope, common specification roles, and optional model profile settings without exposing host repository paths.

- Synthesizes role-tailored `AGENTS.md` guide instructions in the workspace root, establishing agent constraints, workspace boundary rules, permitted in-workspace shell and harness tool execution, fail-stop protocols, cleanroom compilation stub isolation rules for roles declaring stub dependencies, omission of blame directives for roles without feedback capability, model-contingent payload ceiling protection for local or output-constrained models while omitting it for cloud models, and multi-phase instructions for fused roles dynamically derived from constituent role metadata, incorporating use-based micro-binary verification, arbiter self-audits, and defensive code pruning directives requiring pruning uncontracted dead defensive code upon coverage failures.

- Generates starter skeleton files for declared writable target files that are absent from disk, inspecting companion specifications or role templates.

- Writes text files with explicit permissions (read-only, writable, or executable).

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-27T11:35:00Z
LAST_CHANGED: 2026-10-29T15:30:00Z
CHANGE: Derive fused role micro-binaries strictly and dynamically from constituent role names with zero hardcoded role names
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
