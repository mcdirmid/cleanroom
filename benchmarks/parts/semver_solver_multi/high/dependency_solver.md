# dependency_solver interface component

imports: semver_core, semver_range

## Purpose

The dependency_solver interface component defines package registry tracking, release history management, and backtracking dependency resolution across transitive dependency graphs for package ecosystems.

Package ecosystems require deterministic and conflict-free package resolution to select compatible package releases and diagnose conflicting version constraints. Without disciplined repository indexing and backtracking constraint satisfaction algorithms, package managers suffer from silent compatibility regressions, infinite resolution loops, and unexplainable resolution failures. The dependency_solver interface component provides canonical data representations and protocols for package registration, release history retrieval, and backtracking dependency resolution to ensure deterministic and conflict-free package selection.

**Out of scope:** The dependency_solver interface component does not parse raw version strings or compile range expressions (these are handled by semver_core and semver_range), nor does it download package archives from remote network registries, unpack tarballs, or install files into filesystem virtual environments.

## Types and Behavior

Operational failures are categorized into:

- A *resolution conflict error* carrying an error message, an ordered sequence of *conflicting packages*, and a diagnostic *conflict explanation*, inheriting from a *SemVer error*.

- A *package not found error* carrying an error message and a missing *package name*, inheriting from a *SemVer error*.

A *package dependency* represents a prerequisite requirement on a package, carrying a package name and a *range constraint* expressed as a *version range*. A *package release* represents an immutable publication of a package, carrying a package name, a *semantic version*, and an ordered sequence of *declared dependencies*.

A *resolution outcome* summarizes a successful dependency resolution run, carrying a *selected versions mapping* from package names to *semantic versions*, and an ordered sequence of *derivation steps*.

A *package repository* stores and indexes package publications. Repository operations provide:

- Registering package releases, associating a package release with its declared dependencies.

- Retrieving package releases, yielding all registered releases for a package name ordered by version precedence descending, raising package not found error if the package is missing.

- Testing package presence and listing all registered package names.

A *dependency solver* resolves mutually compatible package versions satisfying root requirements. The solver supports *resolving dependencies*, accepting an initial collection of package dependencies, exploring available package releases from the package repository, and backtracking through alternative candidate assignments upon encountering diamond or transitive version conflicts.

Resolution concludes by selecting the highest precedence compatible release for each required package and producing a resolution outcome. When no combination of package releases can satisfy all transitive dependencies, or when a dependency references a package not present in the package repository, the solver raises resolution conflict error identifying the conflicting packages and derivation explanation without allowing package not found error to escape.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:00:00Z
LAST_CHANGED: 2026-10-30T19:00:00Z
CHANGE: Update imports to semver_core and semver_range
SPEC_QA_AUDIT: 2026-10-30T19:00:00Z
-->
