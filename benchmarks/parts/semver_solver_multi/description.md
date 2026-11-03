# semver_solver_multi

The `semver_solver_multi` component realizes semantic version parsing, precedence comparison, range constraint matching, and backtracking package dependency resolution conforming to the SemVer 2.0.0 specification across three decoupled interface components and three concrete implementation components.

## Architecture

The benchmark architecture factors the SemVer specification and package resolution problem into three balanced functional domains:

1. **`semver_core` / `semver_core_impl`** (~110 LOC):
   - **Strict SemVer 2.0.0 Parsing & AST**: Parses semantic versions, validating numeric segment constraints (prohibiting leading zeroes) and separating build metadata from pre-release identifiers into immutable `Version` records.
   - **RFC §11 Precedence Ordering Engine**: Implements strict precedence comparison across major, minor, patch, and mixed numeric/alphanumeric pre-release identifiers, correctly ignoring build metadata in ordering.

2. **`semver_range` / `semver_range_impl`** (~220 LOC):
   - **Disjunctive Normal Form Range Matching**: Parses and evaluates caret (`^`), tilde (`~`), wildcard (`*`, `x`), hyphen (`M1.m1.p1 - M2.m2.p2`), and union (`||`) range expressions.
   - **Boundary & Prerelease Isolation**: Evaluates candidate version satisfaction against compiled comparator clauses, enforcing pre-release isolation rules and zero-major / zero-minor breaking change boundaries.

3. **`dependency_solver` / `dependency_solver_impl`** (~190 LOC):
   - **Indexed Package Registry**: Maintains package publications and declared dependencies, providing sorted release retrieval in descending version precedence order.
   - **Backtracking Dependency Resolution**: Resolves transitive dependency graphs, selecting highest compatible package releases, backtracking on diamond conflicts, and generating diagnostic conflict explanations upon unsatisfiability.
   - **Algorithmic Search Grounding**: Coordinates with `backtracking_solver_ext` for Minimum Remaining Values variable selection, descending precedence candidate evaluation, and conflict trail collection.
