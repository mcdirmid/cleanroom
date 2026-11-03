# Concrete scenarios for semver_range interface

## Scenario 1 — Caret range matching with zero major component

Given: A newly initialized range engine.

1. Parse range constraint `^0.2.3` and evaluate satisfaction for version `0.2.5`.
Observed: Version `0.2.5` matches range `^0.2.3`.

2. Evaluate satisfaction for version `0.3.0` against range `^0.2.3`.
Observed: Version `0.3.0` does not match range `^0.2.3`.

## Scenario 2 — Range parsing whitespace trimming, bare partial rejection, and empty clause rejection

Given: A newly initialized range engine.

1. Parse range expressions with surrounding and clause whitespace `  ^1.0.0  `, `  ~1.0.0  `, and intra-operator whitespace `  >= 1.0.0 < 2.0.0  `.
Observed: All range expressions parse successfully into valid version ranges.

2. Parse empty range ``, whitespace-only range `   `, consecutive union delimiters `1.0.0 || || 2.0.0`, comma-delimited comparators `1.0.0, 2.0.0`, and bare partial numbers `1`, `1.2`, and `1.2 - 2.3` lacking wildcards.
Observed: An invalid range error is raised in each case.

## Scenario 3 — Value object canonical string representation and prerelease boundary evaluation

Given: A newly initialized range engine.

1. Parse range expression `  >=1.0.0 <2.0.0  ` into a version range, inspect its raw text, and convert it to a string.
Observed: The range's raw text property contains trimmed string `>=1.0.0 <2.0.0` and its string representation matches `>=1.0.0 <2.0.0`.

2. Evaluate satisfaction of version `1.0.0-alpha` against range `>=1.0.0 <2.0.0` with explicit pre-release inclusion requested.
Observed: Version `1.0.0-alpha` does not satisfy the range because precedence ordering ranks `1.0.0-alpha` strictly lower than boundary `1.0.0`.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:00:00Z
LAST_CHANGED: 2026-10-30T19:00:00Z
CHANGE: Author semver_range interface concrete scenarios
-->
