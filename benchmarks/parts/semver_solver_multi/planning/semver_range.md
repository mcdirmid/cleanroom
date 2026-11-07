# semver_range interface component

## Intent

Package management ecosystems require robust version range parsing and constraint satisfaction engines to determine compatible versions across dependency specifications. The semver_range interface component defines abstract protocols and data representations for range parsing, disjunctive normal form compilation, and range satisfiability.

By factoring range expression compilation and constraint evaluation into decoupled protocols, the component guarantees deterministic constraint evaluation while keeping package repositories and dependency resolution outside its boundary.

## Factored Contracts

### Typing

- An invalid range error carries an error message and unparseable raw range text.
- A version range carries range expression text.
- A range engine provides range parsing and satisfaction services.

### Contracts

- A range engine parses range expression text into a version range supporting basic comparators, caret ranges, and tilde ranges applied to either full versions or wildcard expressions, hyphen ranges with full version or wildcard endpoints, and union alternatives, trimming surrounding whitespace around range expressions and individual clauses while tolerating optional whitespace between operators and version or wildcard targets, delimiting comparators within clauses strictly by whitespace. [parse_version_range]
- When a range expression contains syntax errors, is empty, consists solely of whitespace, contains empty clauses between union delimiters, uses comma delimiters between comparators, or supplies bare partial versions lacking wildcard tokens across any comparator or hyphen expression, the range engine raises invalid range error carrying the unparseable raw range text. [raise_invalid_range_on_syntax_error]
- A version range tests whether a semantic version matches its constraints. [match_range_against_version]
- Coercing a version range to a string delegates to returning its range expression text. [coerce_range_to_expression_text]
- A version range admits pre-release versions only upon an explicit pre-release inclusion request. [admit_prerelease_on_explicit_request]
- A range engine evaluates whether a semantic version satisfies a version range. [evaluate_version_satisfaction]
- When evaluating version satisfaction, the range engine excludes pre-release versions unless they are explicitly requested or explicitly specified in the range. [filter_unrequested_prerelease_versions]
- When pre-release inclusion is requested, pre-release versions evaluate directly against comparator bounds using precedence comparison without shifting numerical boundaries. [evaluate_prerelease_direct_bounds]

### Woven Contracts

- Range parsing and satisfaction evaluation coordinate so that candidate versions evaluate accurately against compiled comparator constraints. [parse_version_range, evaluate_version_satisfaction]
- Pre-release exclusion during satisfaction testing and direct comparator boundary evaluation compose to handle pre-release constraints without shifting numerical boundaries. [filter_unrequested_prerelease_versions, evaluate_prerelease_direct_bounds, evaluate_version_satisfaction]

## Grounding

### Knowledge Provisions

- Version range models, compilation, and satisfiability engine. [semver_range_service]

### Knowledge Requirements

- Range expression compilation and satisfaction algorithms.
  - Deferred: Realized by concrete realization in semver_range_impl.
- Semantic versioning models, parsing, and precedence comparison engine.
  - Grounded: [semver_core: [semver_core_service]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:00:00Z
LAST_CHANGED: 2026-10-30T19:00:00Z
CHANGE: Author semver_range interface planning specification
SPEC_QA_AUDIT: 2026-10-30T19:00:00Z
-->
