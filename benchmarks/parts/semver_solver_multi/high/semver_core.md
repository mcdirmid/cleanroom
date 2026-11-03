# semver_core interface component

## Purpose

The semver_core interface component defines abstract semantic versioning models, parsing grammar, and precedence comparison rules conforming to SemVer 2.0.0.

Package ecosystems require consistent and unambiguous version identifiers to represent release lifecycles. Without strict adherence to standard version grammar and precedence rules, package managers encounter parse inconsistencies, invalid releases, and nondeterministic version ordering. The semver_core interface component provides canonical data representations and protocols for version parsing, canonical string formatting, and RFC precedence evaluation.

**Out of scope:** The semver_core interface component does not parse or evaluate version range expressions (handled by semver_range), nor does it track package repositories or resolve dependency graphs (handled by dependency_solver).

## Types and Behavior

A *SemVer error* serves as the base error for semantic version operations, carrying a diagnostic *error message*. An *invalid version error* specializes SemVer error, carrying an error message and unparseable *raw version text*.

A *comparator operator* represents a relational comparison between versions, taking the form of *equal*, *not equal*, *less than*, *less than or equal*, *greater than*, or *greater than or equal*.

A *semantic version* represents an immutable semantic version identifier conforming to SemVer 2.0.0, carrying an integer *major version*, an integer *minor version*, an integer *patch version*, an ordered tuple of *pre-release identifiers*, and an ordered tuple of *build metadata identifiers*. The version reports whether it is a *pre-release version* when its pre-release identifiers are non-empty, and provides its canonical *version string*. Coercing a semantic version to a string delegates directly to formatting its canonical version string.

A *version engine* provides version parsing and precedence ordering services. The engine supports *parsing semantic versions*, validating that numeric identifiers contain no leading zeroes, separating dot-separated pre-release segments and plus-prefixed build metadata, raising invalid version error on malformed inputs.

The engine supports *comparing version precedence*, determining ordering precedence between two semantic versions according to SemVer 2.0.0 rules:

- Numerical comparison of major, minor, and patch numbers in order.

- Higher precedence assigned to a normal version over a pre-release version sharing identical major, minor, and patch numbers.

- Segment-by-segment comparison of pre-release identifiers where numeric segments compare as integers, alphanumeric segments compare by ASCII code points, and numeric segments rank below alphanumeric segments.

- Precedence tie-breaking favoring larger sets of pre-release segments when preceding segments match.

- Complete exclusion of build metadata from precedence comparison, such that versions differing solely by build metadata share equal precedence.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:00:00Z
LAST_CHANGED: 2026-10-30T19:00:00Z
CHANGE: Author semver_core interface component specification
SPEC_QA_AUDIT: 2026-10-30T19:00:00Z
-->
