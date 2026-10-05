<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-05T05:31:50Z
CHANGE: Remove internal file alias reference from intent
CODE_HASH: 622e23a4e328
-->

# bazel_target_labels_ext external component

## Intent

Bazel targets can be addressed using apparent, repository-qualified, or shorthand label syntax, causing duplicate graph nodes and broken lookups if compared as raw strings. The bazel_target_labels_ext external component defines the external boundary for normalizing diverse Bazel label formats into canonical package and target coordinates and resolving package directories against a workspace root.

By encapsulating external label grammar parsing, syntax validation, and package directory resolution, the external component guarantees deterministic target identity across Bazel build specifications.

## Factored Contracts

### Contracts

- A caller supplies a raw Bazel target label string when normalizing a label. [normalize_label_supplied]
- A caller supplies a canonical package identifier when resolving a package directory. [resolve_package_dir_supplied]
- A caller supplies a physical workspace root directory when resolving a package directory. [resolve_package_workspace_supplied]
- Target label normalization parses fully qualified repository labels. [parse_repo_qualified_labels]
- Target label normalization parses main repository qualifiers. [parse_main_repo_qualifiers]
- Target label normalization parses package-only shorthand where the target name matches the package name. [parse_package_only_shorthand]
- Target label normalization parses package-relative target names. [parse_package_relative_targets]
- Target label normalization strips main repository prefixes. [strip_main_repo_prefixes]
- Target label normalization expands implicit target identifiers into canonical "//package:target" format. [expand_implicit_target_identifiers]
- Package directory resolution translates canonical package identifiers into relative filesystem directory paths. [translate_package_to_relative_path]
- Package directory resolution resolves package directory paths against physical workspace root directories. [resolve_against_workspace_root]
- Package directory resolution handles workspace root package targets. [handle_workspace_root_targets]
- Target syntax validation enforces Bazel label character set rules and syntax constraints. [enforce_label_syntax_constraints]
- Target syntax validation validates package path segments. [validate_package_path_segments]
- Target syntax validation validates target names. [validate_target_names]
- Target syntax validation rejects malformed label strings. [reject_malformed_labels]
- Target syntax validation rejects ambiguous label strings. [reject_ambiguous_labels]

## Woven Contracts

- Normalizing raw label strings parses diverse formats, strips main repository prefixes, and expands implicit targets into canonical package-target format. [normalize_label_supplied, parse_repo_qualified_labels, parse_main_repo_qualifiers, parse_package_only_shorthand, parse_package_relative_targets, strip_main_repo_prefixes, expand_implicit_target_identifiers]
- Resolving package directories maps canonical package identifiers to relative paths and anchors them to physical workspace roots. [resolve_package_dir_supplied, resolve_package_workspace_supplied, translate_package_to_relative_path, resolve_against_workspace_root, handle_workspace_root_targets]
- Target syntax validation checks character sets and segment boundaries, rejecting malformed or ambiguous strings. [enforce_label_syntax_constraints, validate_package_path_segments, validate_target_names, reject_malformed_labels, reject_ambiguous_labels]
