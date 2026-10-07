<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 0235b6144789
-->

# bazel_target_labels_ext external component

## Intent

Bazel targets can be addressed using apparent, repository-qualified, or shorthand label syntax, causing duplicate graph nodes and broken lookups if compared as raw strings. The bazel_target_labels_ext external component defines the external boundary for normalizing diverse Bazel label formats into canonical package and target coordinates and resolving package directories against a workspace root.

By encapsulating external label grammar parsing, syntax validation, and package directory resolution, the external component guarantees deterministic target identity across Bazel build specifications.

## Grounding

### Knowledge Provisions

- External parsing and normalization of arbitrary Bazel label formats. [bazel_target_label_parsing]
- External translation of package identifiers to relative directory paths. [bazel_package_directory_resolution]
- External validation of Bazel target label syntax and segment constraints. [bazel_label_syntax_validation]
