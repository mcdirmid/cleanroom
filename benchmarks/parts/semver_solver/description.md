# semver_solver

The `semver_solver` component realizes semantic version parsing, precedence comparison, range constraint matching, and backtracking package dependency resolution conforming to the SemVer 2.0.0 specification.

## Capabilities

- **Strict SemVer 2.0.0 Parsing & AST**: Parses semantic versions, validating numeric segment constraints (prohibiting leading zeroes) and separating build metadata from pre-release identifiers.
- **RFC §11 Precedence Ordering Engine**: Implements strict precedence comparison across major, minor, patch, and mixed numeric/alphanumeric pre-release identifiers, correctly ignoring build metadata in ordering.
- **Advanced Range Matching**: Parses and evaluates caret (`^`), tilde (`~`), wildcard, hyphen, and union range expressions, correctly handling zero-major and zero-minor breaking change boundaries.
- **Backtracking Dependency Solver**: Resolves transitive dependency graphs, selecting highest compatible package releases, backtracking on diamond conflicts, and generating diagnostic conflict explanations upon unsatisfiability.
