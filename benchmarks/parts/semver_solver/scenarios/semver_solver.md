# Concrete scenarios for semver_solver interface

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

## Scenario 3 — Caret range matching with zero major component

Given: A newly initialized version engine.

1. Parse range constraint `^0.2.3` and evaluate satisfaction for version `0.2.5`.
Observed: Version `0.2.5` matches range `^0.2.3`.

2. Evaluate satisfaction for version `0.3.0` against range `^0.2.3`.
Observed: Version `0.3.0` does not match range `^0.2.3`.

## Scenario 4 — Package repository registration and sorted retrieval

Given: A newly initialized package repository.

1. Register package release `pkg_a` at version `1.0.0` and release `pkg_a` at version `1.2.0`.
Observed: Package `pkg_a` is present in the repository.

2. Retrieve package releases for `pkg_a`.
Observed: The produced release sequence has version `1.2.0` followed by version `1.0.0`.

## Scenario 5 — Backtracking resolution of diamond dependencies

Given: A dependency solver and package repository where `app` depends on `lib_b` and `lib_c`, `lib_b` at `1.0.0` depends on `lib_d` with constraint `^1.0.0`, `lib_c` at `1.0.0` depends on `lib_d` with constraint `>=1.1.0 <2.0.0`, and `lib_d` has releases `1.0.0`, `1.1.0`, and `1.2.0`.

1. Resolve dependencies for root requirement `app` with constraint `^1.0.0`.
Observed: The produced resolution outcome selects version `1.2.0` for package `lib_d`.

## Scenario 6 — Unsatisfiable dependency conflict raises resolution conflict error

Given: A dependency solver and package repository where `pkg_x` at `1.0.0` requires `pkg_z` at `>=2.0.0`, and `pkg_y` at `1.0.0` requires `pkg_z` at `<2.0.0`.

1. Resolve dependencies for root requirements `pkg_x` at `^1.0.0` and `pkg_y` at `^1.0.0`.
Observed: A resolution conflict error is raised identifying conflicting package `pkg_z`.

2. Resolve dependencies for root requirement on unregistered package `pkg_missing` at `^1.0.0`.
Observed: A resolution conflict error is raised identifying conflicting package `pkg_missing` without raising package not found error.

## Scenario 7 — Rejecting invalid version string with leading zeroes

Given: A newly initialized version engine.

1. Parse version text `1.02.3`.
Observed: An invalid version error is raised carrying raw version text `1.02.3`.

## Scenario 8 — Range parsing whitespace trimming, bare partial rejection, and empty clause rejection

Given: A newly initialized version engine.

1. Parse range expressions with surrounding and clause whitespace `  ^1.0.0  `, `  ~1.0.0  `, and intra-operator whitespace `  >= 1.0.0 < 2.0.0  `.
Observed: All range expressions parse successfully into valid version ranges.

2. Parse empty range ``, whitespace-only range `   `, consecutive union delimiters `1.0.0 || || 2.0.0`, comma-delimited comparators `1.0.0, 2.0.0`, and bare partial numbers `1`, `1.2`, and `1.2 - 2.3` lacking wildcards.
Observed: An invalid range error is raised in each case.

## Scenario 9 — Value object canonical string representation and prerelease boundary evaluation

Given: A newly initialized version engine.

1. Parse version text `1.2.3-beta.1+build.42` into a semantic version and convert it to a string.
Observed: The string representation matches canonical version string `1.2.3-beta.1+build.42`.

2. Parse range expression `  >=1.0.0 <2.0.0  ` into a version range, inspect its raw text, and convert it to a string.
Observed: The range's raw text property contains trimmed string `>=1.0.0 <2.0.0` and its string representation matches `>=1.0.0 <2.0.0`.

3. Evaluate satisfaction of version `1.0.0-alpha` against range `>=1.0.0 <2.0.0` with explicit pre-release inclusion requested.
Observed: Version `1.0.0-alpha` does not satisfy the range because precedence ordering ranks `1.0.0-alpha` strictly lower than boundary `1.0.0`.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-21T20:57:14Z
LAST_CHANGED: 2026-10-27T22:30:00Z
CHANGE: Re-align scenarios with HLS updates for basic comparators and clean value object strings
-->
