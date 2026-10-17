<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:15:00Z
CHANGE: Define workspace_dirtiness interface component
CODE_HASH: dfcd7e0c4f9b
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# workspace_dirtiness interface component

imports: agent_session

## Purpose

The workspace_dirtiness interface component defines operational contracts for evaluating unit dirtiness, resolving companion specification contracts, and inspecting cross-unit dependencies across directory scopes.

Determining whether a unit in a Cleanroom pipeline needs rebuilding or verification requires precise inspection of source timestamps, in-band metadata, upstream contracts, and implicit role dependencies. The workspace_dirtiness interface component establishes contracts for evaluating unit dirty status, extracting companion contract files, and resolving cross-unit dependencies.

**Out of scope:** The workspace_dirtiness interface component does not sort work queues topologically, persist pending work state, or execute build tools; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

An agent session's *workspace dirtiness evaluator* analyzes units within a directory scope to determine whether their forward artifacts require update.

- Evaluates whether a unit is dirty given its role, directory scope, and companion definitions, automatically inspecting and including companion interface contracts without the _impl suffix for any unit ending in _impl, and returning whether the unit is dirty, the list of dirtiness reasons, associated dependency files, and companion contract files.

- When a component type is unmapped in an immediate upstream role, walks the upstream role dependency ancestry until a role mapping that component type is reached for dirtiness propagation.

- Treats feedback role dependencies and star role dependencies as implicit role dependencies for dirty tracking, evaluating a target as dirty when an upstream dependency or any star role dependency changes.

- Inspects in-band metadata across every feedback role target configured for an active auditor role, marking the unit dirty when an audit attribute is missing, unparseable, or stale compared to forward contracts.

- Resolves the companion upstream specification contracts and interface definitions of target units from role definitions, automatically expanding companion interface contracts for units ending in _impl and guiding downstream implementation and verification without leaking peer implementation code.

- Extracts cross-unit dependencies for a designated unit across declared parts in repository scope.
