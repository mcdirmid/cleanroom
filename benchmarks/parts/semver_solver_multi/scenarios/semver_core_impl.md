# Concrete scenarios for semver_core_impl implementation

## Reused from the interface

### Scenario 1 — Parsing standard version and precedence comparison

Given: A newly initialized version engine.

1. Parse version text `1.2.3` and version text `1.2.4-alpha`.
Observed: Version `1.2.3` has major 1, minor 2, patch 3, and version `1.2.4-alpha` is identified as a pre-release version.
Realized by: Matching against regular expression patterns, extracting numeric groups, and populating immutable semantic version attributes.

2. Compare precedence between `1.2.3` and `1.2.4-alpha`.
Observed: Version `1.2.3` has lower precedence than `1.2.4-alpha`.
Realized by: Comparing major, minor, and patch components numerically in order, where patch 3 is less than patch 4, and consulting pre-release identifiers only after those components tie.

### Scenario 2 — Pre-release precedence ordering with mixed numeric segments

Given: A newly initialized version engine.

1. Parse pre-release versions `1.0.0-beta.2` and `1.0.0-beta.11`.
Observed: Both versions are parsed with 2 pre-release segments.
Realized by: Splitting pre-release strings on dot characters and classifying individual segments as numeric or alphanumeric.

2. Compare precedence between `1.0.0-beta.2` and `1.0.0-beta.11`.
Observed: Version `1.0.0-beta.2` has lower precedence than `1.0.0-beta.11`.
Realized by: Comparing matching initial segment `beta` as ASCII strings, then comparing second segment numerically where integer 2 is less than integer 11.

### Scenario 3 — Rejecting invalid version string with leading zeroes

Given: A newly initialized version engine.

1. Parse version text `1.02.3`.
Observed: An invalid version error is raised carrying raw version text `1.02.3`.
Realized by: Detecting leading zero on numeric minor segment `02` during regular expression parsing and raising invalid version error.

### Scenario 4 — Canonical string representation and build metadata exclusion

Given: A newly initialized version engine.

1. Parse version text `1.2.3-beta.1+build.42` into a semantic version and convert it to a string.
Observed: The string representation matches canonical version string `1.2.3-beta.1+build.42`.
Realized by: Joining components with dot delimiters, prefixing prerelease with hyphen, and prefixing build metadata with plus.

2. Compare precedence between `1.0.0+build.1` and `1.0.0+build.2`.
Observed: Precedence comparison evaluates to zero indicating equal precedence.
Realized by: Completely ignoring build metadata segments during precedence comparison.

## Implementation-only

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:00:00Z
LAST_CHANGED: 2026-10-30T19:00:00Z
CHANGE: Author semver_core_impl implementation concrete scenarios
-->
