# semver_solver interface component

## Purpose

The semver_solver interface component defines abstract semantic versioning models, precedence comparison rules, range constraint matching, package registry tracking, and backtracking dependency resolution for package ecosystems.

Package ecosystems depend on precise semantic versioning contracts to avoid dependency hell, breaking changes, and conflicting version constraints. Without rigorous adherence to standard precedence rules and constraint satisfiability algorithms, package managers suffer from silent compatibility regressions, infinite resolution loops, and unexplainable resolution failures. The semver_solver interface component provides canonical data representations and protocols for version parsing, RFC precedence evaluation, range satisfiability, and backtracking dependency resolution to ensure deterministic and conflict-free package selection.

**Out of scope:** The semver_solver interface component does not download package archives from remote network registries, unpack tarballs, or install files into filesystem virtual environments; these are handled by other components.

## Types and Behavior

A *SemVer error* serves as the base error for semantic version operations, carrying a diagnostic *error message*. Operational failures are categorized into:

- An *invalid version error* carrying an error message and unparseable *raw version text*.

- An *invalid range error* carrying an error message and unparseable *raw range text*.

- A *resolution conflict error* carrying an error message, an ordered sequence of *conflicting packages*, and a diagnostic *conflict explanation*.

- A *package not found error* carrying an error message and a missing *package name*.

A *comparator operator* represents a relational comparison between versions, taking the form of *equal*, *not equal*, *less than*, *less than or equal*, *greater than*, or *greater than or equal*.

A *semantic version* represents an immutable semantic version identifier conforming to SemVer 2.0.0, carrying an integer *major version*, an integer *minor version*, an integer *patch version*, an ordered tuple of *pre-release identifiers*, and an ordered tuple of *build metadata identifiers*. The version reports whether it is a *pre-release version* when its pre-release identifiers are non-empty, and provides its canonical *version string*. Coercing a semantic version to a string delegates directly to formatting its canonical version string.

A *version range* represents an immutable version constraint expression, carrying its canonical *range expression text*. The range tests whether a semantic version *matches* its constraints, admitting pre-release versions only upon an explicit *pre-release inclusion* request. Coercing a version range to a string delegates to returning its range expression text.

A *package dependency* represents a prerequisite requirement on a package, carrying a package name and a *range constraint*. A *package release* represents an immutable publication of a package, carrying a package name, a semantic version, and an ordered sequence of *declared dependencies*.

A *resolution outcome* summarizes a successful dependency resolution run, carrying a *selected versions mapping* from package names to semantic versions, and an ordered sequence of *derivation steps*.

A *version engine* provides parsing, precedence ordering, and range matching services. The engine supports *parsing semantic versions*, validating that numeric identifiers contain no leading zeroes, separating dot-separated pre-release segments and plus-prefixed build metadata, raising invalid version error on malformed inputs.

The engine supports *comparing version precedence*, determining ordering precedence between two semantic versions according to SemVer 2.0.0 rules:

- Numerical comparison of major, minor, and patch numbers in order.

- Higher precedence assigned to a normal version over a pre-release version sharing identical major, minor, and patch numbers.

- Segment-by-segment comparison of pre-release identifiers where numeric segments compare as integers, alphanumeric segments compare by ASCII code points, and numeric segments rank below alphanumeric segments.

- Precedence tie-breaking favoring larger sets of pre-release segments when preceding segments match.

- Complete exclusion of build metadata from precedence comparison, such that versions differing solely by build metadata share equal precedence.

The engine supports *parsing version ranges*, converting range expression text into a version range supporting basic comparators (`==`, `=`, `!=`, `<`, `<=`, `>`, `>=`), caret ranges (`^`), tilde ranges (`~`), wildcards (`*`, `x`, `X`, `M.x`, `M.*`, `M.m.x`, `M.m.*`), hyphen ranges (`M1.m1.p1 - M2.m2.p2`), and union alternatives (`||`), trimming surrounding whitespace around range expressions and individual clauses while tolerating optional whitespace between relational or prefix operators and version targets, delimiting comparators within clauses strictly by whitespace, raising invalid range error when the expression is empty, consists solely of whitespace, contains empty clauses between union alternatives, uses comma delimiters between comparators, supplies bare partial versions lacking wildcard tokens across any comparator or hyphen expression, or violates range syntax. The engine supports *evaluating version satisfaction*, testing whether a semantic version satisfies a version range while excluding pre-release versions unless explicitly requested or explicitly specified in the range. When pre-release inclusion is requested, pre-release versions evaluate directly against comparator bounds using precedence comparison without shifting numerical boundaries.

A *package repository* stores and indexes package publications. Repository operations provide:

- Registering package releases, associating a package release with its declared dependencies.

- Retrieving package releases, yielding all registered releases for a package name ordered by version precedence descending, raising package not found error if the package is missing.

- Testing package presence and listing all registered package names.

A *dependency solver* resolves mutually compatible package versions satisfying root requirements. The solver supports *resolving dependencies*, accepting an initial collection of package dependencies, exploring available package releases from the package repository, and backtracking through alternative candidate assignments upon encountering diamond or transitive version conflicts.

Resolution concludes by selecting the highest precedence compatible release for each required package and producing a resolution outcome. When no combination of package releases can satisfy all transitive dependencies, or when a dependency references a package not present in the package repository, the solver raises resolution conflict error identifying the conflicting packages and derivation explanation without allowing package not found error to escape.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-27T02:19:04Z
LAST_CHANGED: 2026-10-27T22:30:00Z
CHANGE: Remove overconstrained exact range text normalization, clarify basic equality operators and prerelease boundary satisfaction
SPEC_QA_AUDIT: 2026-10-27T02:19:04Z
-->
