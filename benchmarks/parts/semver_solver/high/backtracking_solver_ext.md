# backtracking_solver_ext external component

## Purpose

The backtracking_solver_ext external component provides algorithmic reference knowledge for depth-first search with Minimum Remaining Values variable ordering, descending precedence value exploration, and conflict trail collection.

Resolving dependency constraints across mutually dependent software packages requires exploring combinatorial solution spaces with search heuristics. Without deterministic variable selection heuristics, consistent value ordering, and structured conflict recording, solvers exhibit erratic search latencies, fail to find existing compatible configurations, or lack informative conflict diagnostics on unsatisfiable diamond dependencies. The backtracking_solver_ext external component establishes these algorithmic reference mechanics independently of application requirements.

**Out of scope:** The backtracking_solver_ext external component does not define application services, public API error-handling policies, version parsing, repository storage, or network manifests; these are handled by other components.

## Grounding Gaps Covered

The backtracking_solver_ext component provides algorithmic mechanics for depth-first dependency search and conflict attribution.

Grounding gaps covered include:

- Variable selection prioritization: Unassigned packages are prioritized using the Minimum Remaining Values heuristic, selecting the unassigned package with the fewest satisfying candidate releases, with lexical tie-breaking on package names.

- Value exploration ordering: Candidate releases for the selected package are evaluated in descending version precedence order, prioritizing higher versions over lower versions.

- Incremental constraint propagation: When a candidate release is assigned, its declared dependency constraints merge into the accumulated constraint mapping, updating viability for remaining unassigned packages.

- Backtracking state management: Search maintains a decision stack recording assignments and newly introduced constraints. When candidate options for a package exhaust, the solver undoes the most recent assignment and restores prior constraint mappings.

- Conflict trail compilation: When a package possesses zero viable releases under accumulated constraints, the failing requirement expressions and source packages are appended to a conflict trail. If all search branches exhaust without a complete assignment, the conflict trail provides diagnostic explanations for the unsatisfiable dependency graph.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-27T03:40:00Z
LAST_CHANGED: 2026-10-27T22:35:00Z
CHANGE: Focus backtracking_solver_ext strictly on algorithmic reference knowledge and search heuristics without application requirements
SPEC_QA_AUDIT: 2026-10-27T02:19:04Z
-->
