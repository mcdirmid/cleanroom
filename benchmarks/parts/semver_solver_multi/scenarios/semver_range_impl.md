# Concrete scenarios for semver_range_impl implementation

## Reused from the interface

### Scenario 1 — Caret range matching with zero major component

Given: A newly initialized range engine.

1. Parse range constraint `^0.2.3` and evaluate satisfaction for version `0.2.5`.
Observed: Version `0.2.5` matches range `^0.2.3`.
Realized by: Expanding caret prefix on zero major version to bounds `>=0.2.3 <0.3.0` and verifying candidate version satisfies both bounds.

2. Evaluate satisfaction for version `0.3.0` against range `^0.2.3`.
Observed: Version `0.3.0` does not match range `^0.2.3`.
Realized by: Evaluating upper bound inequality `<0.3.0` against version `0.3.0` which fails strictly.

### Scenario 2 — Range parsing whitespace trimming, bare partial rejection, and empty clause rejection

Given: A newly initialized range engine.

1. Parse range expressions with surrounding and clause whitespace `  ^1.0.0  `, `  ~1.0.0  `, and intra-operator whitespace `  >= 1.0.0 < 2.0.0  `.
Observed: All range expressions parse successfully into valid version ranges.
Realized by: Trimming leading and trailing whitespace on range input and individual comparator clauses, and accepting optional whitespace between operators and version targets.

2. Parse empty range ``, whitespace-only range `   `, consecutive union delimiters `1.0.0 || || 2.0.0`, comma-delimited comparators `1.0.0, 2.0.0`, and bare partial numbers `1`, `1.2`, and `1.2 - 2.3` lacking wildcards.
Observed: An invalid range error is raised in each case.
Realized by: Validating that the trimmed expression and each split union clause are non-empty, rejecting comma delimiters within clauses, and detecting that partial tokens without wildcard characters violate range grammar.

### Scenario 3 — Value object canonical string representation and prerelease boundary evaluation

Given: A newly initialized range engine.

1. Parse range expression `  >=1.0.0 <2.0.0  ` into a version range, inspect its raw text, and convert it to a string.
Observed: The range's raw text property contains trimmed string `>=1.0.0 <2.0.0` and its string representation matches `>=1.0.0 <2.0.0`.
Realized by: Storing trimmed expression text in the immutable version range record.

2. Evaluate satisfaction of version `1.0.0-alpha` against range `>=1.0.0 <2.0.0` with explicit pre-release inclusion requested.
Observed: Version `1.0.0-alpha` does not satisfy the range because precedence ordering ranks `1.0.0-alpha` strictly lower than boundary `1.0.0`.
Realized by: Evaluating candidate version directly against lower bound `>=1.0.0` via precedence comparison without shifting numerical boundaries.

### Scenario 4 — Operator-wildcard composition and wildcard hyphen range matching

Given: A newly initialized range engine.

1. Parse range expressions combining operators with wildcards `  >= 1.x  `, `  != 1.x  `, `  ^ 1.x  `, `  ~ 1.x  `, and `  >= *  `, and wildcard hyphen range `  1.0.0 - 2.x  `.
Observed: All expressions parse successfully into valid version ranges.
Realized by: Compiling relational and prefix operators with wildcard operands and hyphen ranges with wildcard endpoints into comparator boundary inequalities.

2. Evaluate satisfaction of version `1.5.0` against `>=1.x`, `1.2.0` against `!=1.x`, `1.5.0` against `^1.x`, `2.5.0` against `1.0.0 - 2.x`, and `3.0.0` against `1.0.0 - 2.x`.
Observed: Version `1.5.0` matches range `>=1.x`, version `1.2.0` does not match range `!=1.x`, version `1.5.0` matches range `^1.x`, version `2.5.0` matches range `1.0.0 - 2.x`, and version `3.0.0` does not match range `1.0.0 - 2.x`.
Realized by: Testing candidate versions against compiled comparator inequalities.

## Implementation-only

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:00:00Z
LAST_CHANGED: 2026-10-30T19:00:00Z
CHANGE: Author semver_range_impl implementation concrete scenarios
-->
