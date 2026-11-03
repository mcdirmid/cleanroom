# semver_range interface component

imports: semver_core

## Purpose

The semver_range interface component defines abstract version constraint expressions, range syntax parsing, and constraint satisfiability algorithms for semantic versioning ecosystems.

Package dependencies rely on range expressions to constrain acceptable releases without hardcoding single versions. Without rigorous range grammar compilation and constraint satisfiability algorithms, package managers suffer from false constraint evaluations and unexpected version rejections. The semver_range interface component provides canonical data representations and protocols for range expression parsing, disjunctive normal form compilation, and version satisfiability.

**Out of scope:** The semver_range interface component does not define core semantic version syntax or RFC precedence rules (these are defined by semver_core), nor does it track package repositories or resolve dependency graphs (these are handled by dependency_solver).

## Types and Behavior

An *invalid range error* specializes a *SemVer error*, carrying an error message and unparseable *raw range text*.

A *version range* represents an immutable version constraint expression, carrying its canonical *range expression text*. The range tests whether a *semantic version* *matches* its constraints, admitting pre-release versions only upon an explicit *pre-release inclusion* request. Coercing a version range to a string delegates to returning its range expression text.

A *range engine* provides range parsing and constraint matching services. The engine supports *parsing version ranges*, converting range expression text into a version range supporting basic comparators (`==`, `=`, `!=`, `<`, `<=`, `>`, `>=`), caret ranges (`^`), tilde ranges (`~`), wildcards (`*`, `x`, `X`, `M.x`, `M.*`, `M.m.x`, `M.m.*`), hyphen ranges (`M1.m1.p1 - M2.m2.p2`), and union alternatives (`||`), trimming surrounding whitespace around range expressions and individual clauses while tolerating optional whitespace between relational or prefix operators and version targets, delimiting comparators within clauses strictly by whitespace, raising invalid range error when the expression is empty, consists solely of whitespace, contains empty clauses between union alternatives, uses comma delimiters between comparators, supplies bare partial versions lacking wildcard tokens across any comparator or hyphen expression, or violates range syntax.

The engine supports *evaluating version satisfaction*, testing whether a semantic version satisfies a version range while excluding pre-release versions unless explicitly requested or explicitly specified in the range. When pre-release inclusion is requested, pre-release versions evaluate directly against comparator bounds using precedence comparison without shifting numerical boundaries.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:00:00Z
LAST_CHANGED: 2026-10-30T19:00:00Z
CHANGE: Author semver_range interface component specification
SPEC_QA_AUDIT: 2026-10-30T19:00:00Z
-->
