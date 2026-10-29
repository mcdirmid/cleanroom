# semver_solver interface component

## Intent

Package management ecosystems require robust semantic versioning contracts and dependency resolution engines to select compatible package releases, prevent breaking changes, and diagnose incompatible requirement graphs. The semver_solver interface component defines abstract protocols and data representations for SemVer 2.0.0 parsing, RFC precedence comparison, range satisfiability, package repository tracking, and backtracking dependency resolution.

By factoring version tokenization, precedence evaluation, range compilation, and constraint solving into decoupled protocols, the component guarantees deterministic package selection and clear conflict reporting while keeping archive downloads, tarball unpacking, and filesystem installation outside its boundary.

## Factored Contracts

### Typing

- A SemVer error carries a diagnostic error message.
- An invalid version error carries an error message and unparseable raw version text.
- An invalid range error carries an error message and unparseable raw range text.
- A resolution conflict error carries an error message, an ordered sequence of conflicting packages, and a diagnostic conflict explanation.
- A package not found error carries an error message and a missing package name.
- A comparator operator takes the form of equal, not equal, less than, less than or equal, greater than, or greater than or equal.
- A semantic version carries a major version, a minor version, a patch version, an ordered tuple of pre-release identifiers, and an ordered tuple of build metadata identifiers.
- A version range carries range expression text.
- A package dependency carries a package name and a range constraint.
- A package release carries a package name, a semantic version, and an ordered sequence of declared dependencies.
- A resolution outcome carries a selected versions mapping from package names to semantic versions and an ordered sequence of derivation steps.
- A version engine provides parsing, precedence ordering, and range matching services.
- A package repository stores and indexes package publications.
- A dependency solver computes compatible version assignments through backtracking search.

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
- A version engine parses range expression text into a version range supporting basic comparators, caret ranges, tilde ranges, wildcards, hyphen ranges, and union alternatives, trimming surrounding whitespace around range expressions and individual clauses while tolerating optional whitespace between operators and version targets, delimiting comparators within clauses strictly by whitespace. [parse_version_range]
- When a range expression contains syntax errors, is empty, consists solely of whitespace, contains empty clauses between union delimiters, uses comma delimiters between comparators, or supplies bare partial versions lacking wildcard tokens across any comparator or hyphen expression, the version engine raises invalid range error carrying the unparseable raw range text. [raise_invalid_range_on_syntax_error]
- A version range tests whether a semantic version matches its constraints. [match_range_against_version]
- Coercing a version range to a string delegates to returning its range expression text. [coerce_range_to_expression_text]
- A version range admits pre-release versions only upon an explicit pre-release inclusion request. [admit_prerelease_on_explicit_request]
- A version engine evaluates whether a semantic version satisfies a version range. [evaluate_version_satisfaction]
- When evaluating version satisfaction, the version engine excludes pre-release versions unless they are explicitly requested or explicitly specified in the range. [filter_unrequested_prerelease_versions]
- When pre-release inclusion is requested, pre-release versions evaluate directly against comparator bounds using precedence comparison without shifting numerical boundaries. [evaluate_prerelease_direct_bounds]
- A package repository registers a package release together with its declared dependencies. [register_package_release]
- A package repository retrieves all releases for a package name ordered by descending version precedence. [retrieve_sorted_package_releases]
- When a requested package name is absent from the repository, the package repository raises package not found error carrying the missing package name. [raise_package_not_found_on_missing_name]
- A package repository tests whether a package name is present in storage. [test_package_presence]
- A package repository lists all registered package names. [list_all_registered_packages]
- A dependency solver resolves package dependencies by exploring available package releases from the package repository. [resolve_package_dependencies]
- When a candidate assignment conflicts with an existing assignment through diamond or transitive requirements, the dependency solver backtracks through alternative candidate assignments. [backtrack_alternative_candidate_assignments]
- A dependency solver selects the highest precedence compatible release for each required package upon concluding resolution. [select_highest_precedence_compatible_release]
- A dependency solver produces a resolution outcome carrying selected versions and derivation steps. [produce_resolution_outcome]
- When no combination of package releases satisfies all transitive dependencies, or when a dependency references a package not present in the package repository, the dependency solver raises resolution conflict error identifying the conflicting packages and derivation explanation without allowing package not found error to escape. [raise_resolution_conflict_on_unsatisfiable_constraints]

### Woven Contracts

- Version parsing, precedence evaluation, and range matching coordinate with package repository indexing and backtracking dependency resolution so that every selected version satisfies its accumulated constraints. [parse_semantic_version, compare_version_numeric_components, compare_prerelease_segments, parse_version_range, evaluate_version_satisfaction, register_package_release, retrieve_sorted_package_releases, resolve_package_dependencies, raise_resolution_conflict_on_unsatisfiable_constraints]
- Pre-release exclusion during satisfaction testing and descending precedence ordering of repository releases together determine which candidate releases backtracking search explores first. [filter_unrequested_prerelease_versions, retrieve_sorted_package_releases, backtrack_alternative_candidate_assignments, select_highest_precedence_compatible_release]

## Grounding

### Knowledge Provisions

- Semantic versioning models, precedence comparison, range matching, package repository, and backtracking solver. [semver_solver_core_service]

### Knowledge Requirements

- Parsing regexes, precedence ordering algorithms, range expression compilation, repository indexing, and backtracking constraint satisfaction.
  - Deferred: Realized by concrete realization in semver_solver_impl.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-27T02:19:04Z
LAST_CHANGED: 2026-10-27T22:30:00Z
CHANGE: Re-align planning contracts with HLS updates for basic comparators and clean value object strings
SPEC_QA_AUDIT: 2026-10-27T02:19:04Z
-->
