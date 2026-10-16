<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:15:00Z
CHANGE: Define workspace_dirtiness_impl concrete scenarios
CODE_HASH: d2855c7e99e9
-->

# Concrete scenarios for `workspace_dirtiness_impl` (implementation)

## Scenario 1 — Producer unit dirtiness with star role dependencies

Given: an implementation unit cleaned at timestamp T1, with a star-role dependency on interface specifications modified at timestamp T2 > T1.

1. The caller invokes `evaluate_unit_dirty`.
   Observed: returns dirty `True` and lists the star dependency modification reason.

2. The caller invokes `resolve_contract_files`.
   Observed: returns companion low-level interface and planning specifications while omitting silent cross-role dependencies.

## Scenario 2 — Cross-unit dependency extraction across repository scope

Given: a unit in a part declaring cross-unit dependencies on companion parts.

1. The caller invokes `extract_cross_unit_dependencies`.
   Observed: returns resolved pairs of `(part_dir, unit_name)` for all declared dependencies.
