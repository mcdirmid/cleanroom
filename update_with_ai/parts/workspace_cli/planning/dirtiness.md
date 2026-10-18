<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:15:00Z
CHANGE: Define dirtiness planning specification
CODE_HASH: 29c505eaa484
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# dirtiness interface component

## Intent

Determining whether a unit in a Cleanroom pipeline needs rebuilding or verification requires precise inspection of source timestamps, in-band metadata, upstream contracts, and implicit role dependencies. The dirtiness interface component establishes contracts for evaluating unit dirty status, extracting companion contract files, and resolving cross-unit dependencies across directory scopes.

## Factored Contracts

### Typing

- A workspace dirtiness evaluator operates within the agent session lifecycle tier.

### Contracts

- The workspace dirtiness evaluator evaluates whether a unit is dirty given its role, directory scope, and companion definitions, automatically inspecting companion interface contracts for units ending in _impl, inspecting canonical lifecycle metadata from the main repository when available to prevent projected workspace files from being misdiagnosed as dirty due to omitted lifecycle timestamps, walking upstream role ancestry when a component type is unmapped, and returning whether the unit is dirty, the list of dirtiness reasons, associated dependency files, and companion contract files. [evaluate_unit_dirtiness]
- The workspace dirtiness evaluator treats feedback role dependencies and star role dependencies as implicit role dependencies for dirty tracking. [evaluate_implicit_and_star_dirtiness]
- The workspace dirtiness evaluator inspects in-band metadata across every feedback role target configured for an active auditor role, marking the unit dirty when an audit attribute is missing, unparseable, or stale compared to forward contracts. [evaluate_auditor_target_dirtiness]
- The workspace dirtiness evaluator resolves companion upstream specification contracts and interface definitions of target units from role definitions, automatically expanding companion interface contracts for units ending in _impl and avoiding peer implementation code leakage. [resolve_companion_contract_files]
- The workspace dirtiness evaluator extracts cross-unit dependencies for a designated unit across declared parts in repository scope. [extract_cross_unit_dependencies]

### Woven Contracts

- When evaluating unit status in a role workspace, the dirtiness evaluator inspects in-band metadata, tests upstream timestamps, discovers companion contracts, and resolves cross-unit dependencies. [evaluate_unit_dirtiness, evaluate_implicit_and_star_dirtiness, evaluate_auditor_target_dirtiness, resolve_companion_contract_files, extract_cross_unit_dependencies]

## Grounding

### Knowledge Provisions

- Unit dirtiness evaluation, companion contract resolution, and cross-unit dependency services. [workspace_dirtiness_service]

### Knowledge Requirements

- In-band source metadata extraction and evaluation.
  - Deferred: Provided by workspace dirtiness evaluator implementation.
- Role definition resolution and pattern matching.
  - Deferred: Provided by workspace dirtiness evaluator implementation.
- Scope file resolution and dirtiness evaluation mechanics.
  - Deferred: Provided by workspace dirtiness evaluator implementation.
