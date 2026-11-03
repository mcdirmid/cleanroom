# Concrete scenarios for semver_core interface

## Scenario 1 — Parsing standard version and precedence comparison

Given: A newly initialized version engine.

1. Parse version text `1.2.3` and version text `1.2.4-alpha`.
Observed: Version `1.2.3` has major 1, minor 2, patch 3, and version `1.2.4-alpha` is identified as a pre-release version.

2. Compare precedence between `1.2.3` and `1.2.4-alpha`.
Observed: Version `1.2.3` has lower precedence than `1.2.4-alpha`.

## Scenario 2 — Pre-release precedence ordering with mixed numeric segments

Given: A newly initialized version engine.

1. Parse pre-release versions `1.0.0-beta.2` and `1.0.0-beta.11`.
Observed: Both versions are parsed with 2 pre-release segments.

2. Compare precedence between `1.0.0-beta.2` and `1.0.0-beta.11`.
Observed: Version `1.0.0-beta.2` has lower precedence than `1.0.0-beta.11`.

## Scenario 3 — Rejecting invalid version string with leading zeroes

Given: A newly initialized version engine.

1. Parse version text `1.02.3`.
Observed: An invalid version error is raised carrying raw version text `1.02.3`.

## Scenario 4 — Canonical string representation and build metadata exclusion

Given: A newly initialized version engine.

1. Parse version text `1.2.3-beta.1+build.42` into a semantic version and convert it to a string.
Observed: The string representation matches canonical version string `1.2.3-beta.1+build.42`.

2. Compare precedence between `1.0.0+build.1` and `1.0.0+build.2`.
Observed: Precedence comparison evaluates to zero indicating equal precedence.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:00:00Z
LAST_CHANGED: 2026-10-30T19:00:00Z
CHANGE: Author semver_core interface concrete scenarios
-->
