# semver_core interface component

## Intent

Package management ecosystems require robust semantic versioning contracts to parse version identifiers and evaluate precedence rules accurately. The semver_core interface component defines abstract protocols and data representations for SemVer 2.0.0 parsing, canonical formatting, and RFC precedence comparison.

By factoring version tokenization and precedence evaluation into decoupled protocols, the component guarantees deterministic version comparison and standard-compliant syntax validation while keeping range expressions and package repositories outside its boundary.

## Factored Contracts

### Typing

- A SemVer error carries a diagnostic error message.
- An invalid version error carries an error message and unparseable raw version text.
- A comparator operator takes the form of equal, not equal, less than, less than or equal, greater than, or greater than or equal.
- A semantic version carries a major version, a minor version, a patch version, an ordered tuple of pre-release identifiers, and an ordered tuple of build metadata identifiers.
- A version engine provides parsing and precedence ordering services.

### Contracts

- A version engine parses semantic version text into major, minor, and patch numbers together with dot-separated pre-release identifiers and plus-prefixed build metadata identifiers. [parse_semantic_version]
- A version engine rejects numeric identifiers containing leading zeroes during version parsing. [reject_leading_zero_numeric_identifiers]
- When version text violates SemVer 2.0.0 syntax, the version engine raises invalid version error carrying the unparseable raw version text. [raise_invalid_version_on_syntax_error]
- A semantic version reports itself as a pre-release version when its pre-release identifiers are non-empty. [report_prerelease_status]
- A semantic version provides its canonical version string. [format_canonical_version_string]
- Coercing a semantic version to a string delegates directly to formatting its canonical version string. [coerce_version_to_canonical_string]
- A version engine compares major, minor, and patch numbers numerically in order of precedence. [compare_version_numeric_components]
- A normal version has higher precedence than a pre-release version sharing identical major, minor, and patch numbers. [prefer_normal_over_prerelease]
- A version engine compares pre-release identifiers segment by segment where numeric segments compare as integers and alphanumeric segments compare by ASCII code points. [compare_prerelease_segments]
- Numeric pre-release segments have lower precedence than alphanumeric pre-release segments. [rank_numeric_below_alphanumeric_prerelease]
- A larger set of pre-release segments has higher precedence than a smaller set when preceding segments match. [break_prerelease_ties_by_segment_count]
- A version engine excludes build metadata from precedence comparison so that versions differing solely by build metadata share equal precedence. [exclude_build_metadata_from_precedence]

### Woven Contracts

- Version parsing and precedence evaluation coordinate so that candidate versions are parsed into valid records and evaluated according to RFC precedence ordering. [parse_semantic_version, compare_version_numeric_components, compare_prerelease_segments, prefer_normal_over_prerelease, exclude_build_metadata_from_precedence]

## Grounding

### Knowledge Provisions

- Semantic versioning models, parsing, and precedence comparison engine. [semver_core_service]

### Knowledge Requirements

- Parsing regexes and precedence ordering algorithms.
  - Deferred: Realized by concrete realization in semver_core_impl.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:00:00Z
LAST_CHANGED: 2026-10-30T19:00:00Z
CHANGE: Author semver_core interface planning specification
SPEC_QA_AUDIT: 2026-10-30T19:00:00Z
-->
