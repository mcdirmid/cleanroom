<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:40:00Z
CHANGE: Define pending interface specification
CODE_HASH: 882c6083a5d6
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# pending interface component

imports: session, cleanroom_files_ext

## Purpose

The pending interface component defines operational contracts for tracking pending target files, persisting local work buffers, and evaluating pending target dirtiness within role workspaces.

Autonomous agents operating inside isolated role workspaces require persistent tracking of assigned tasks across command invocations to prevent leaving incomplete work behind when querying new batches. The pending interface component establishes contracts for inspecting pending targets, updating the pending buffer file, removing submitted or blamed targets, and verifying whether assigned targets remain dirty across local and canonical workspaces.

**Out of scope:** The pending interface component does not schedule directory-scoped dependency graphs, parse tool CLI flags, or transfer workspace files; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; workspace file conventions are delegated to cleanroom_files_ext.

## Types and Behavior

An agent session's *workspace pending manager* tracks active pending tasks within a role workspace.

The workspace pending manager:

- Inspects the local pending work buffer file, returning active pending target paths or an empty sequence when no buffer exists.

- Records assigned ready target paths into the pending work buffer file, establishing active task ownership.

- Removes resolved targets from the pending work buffer file upon submission or blame attribution.

- Clears the pending work buffer file when all assigned tasks in the role workspace evaluate clean.

- Evaluates whether an assigned pending target remains dirty by checking in-band source metadata across the role workspace and main repository, treating feedback and star-role dependencies as implicit dependencies, and materializing starter templates when missing.
