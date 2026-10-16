<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T18:50:00Z
CHANGE: Author workspace_scaffold interface specification
CODE_HASH: de4a9901dd26
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_scaffold interface component

imports: agent_session, cleanroom_files_ext, workspace_roles

## Purpose

The workspace_scaffold interface component defines operational contracts for deploying runner zipapps, serializing role metadata, synthesizing role-tailored AGENTS.md guide instructions, and generating missing target skeletons within Cleanroom role workspaces.

Commissioned role workspaces require specialized executable tooling, in-band configuration, explicit agent operating instructions, and starter skeletons for new targets. Coupling this file synthesis and runner bundling directly into filesystem directory creation inflates workspace initialization logic and hinders isolated testing of agent guide formatting and tool packaging. The workspace_scaffold interface component establishes dedicated contracts for packaging standalone zipapp runners, writing role descriptor configuration without exposing host repository paths, formatting role-specific AGENTS.md documents with strict boundary tripwires and fail-stop protocols, and generating initial starter skeletons from companion specifications or templates.

**Out of scope:** The workspace_scaffold interface component does not create top-level workspace directory trees, resolve workspace paths, or synchronize implementation files; these are handled by other components.

**Delegated:** Role metadata resolution and role definitions are delegated to workspace_roles or workspace_registry. File naming conventions for the role descriptor configuration are delegated to cleanroom_files_ext.

## Types and Behavior

An agent session's *workspace scaffolder* prepares role runner tools, metadata configuration, role agent instructions, and target starter skeletons within commissioned role workspaces.

The workspace scaffolder:

- Deploys executable runner tools into the `bin/` directory of the workspace, packaging the work, check files, submit, blame, fail, and coverage runners as standalone zipapp executables with execution permissions.

- Writes workspace role configuration into a hidden role descriptor file recording role identity, directory scope, and optional model profile settings without exposing host repository paths.

- Synthesizes role-tailored `AGENTS.md` guide instructions in the workspace root, establishing agent constraints, boundary rules, command execution tripwires, in-workspace file inspection permissions, and fail-stop protocols.

- Generates starter skeleton files for declared writable target files that are absent from disk, inspecting companion specifications or role templates.

- Writes text files with explicit permissions (read-only, writable, or executable).
