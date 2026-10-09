<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 9e8d41068cb1
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# bazel_target_impl implementation component

imports: dag_storage, file_paths, bazel_target_labels_ext
implements: bazel_target

## Intent

Bazel targets can be addressed using apparent, repository-qualified, or shorthand syntax, creating potential node duplication and broken package lookups. The bazel_target_impl implementation component strips repository prefixes, infers implicit target basenames, and resolves package directory locations against the workspace root.

By delegating label normalization and package resolution to the bazel_target_labels_ext external boundary, the implementation produces canonical dag nodes and reliable workspace directory mappings.

## Factored Contracts

### Contracts

- The bazel target strips repository qualifiers when normalizing raw target labels. [strip_repository_qualifiers]
- The bazel target expands omitted target names when normalizing raw target labels. [expand_omitted_target_names]
- The bazel target derives node directories by extracting package directory paths relative to a workspace root. [derive_node_directories_relative_to_root]

### Woven Contracts

- Normalizing target labels invokes external label parsing to strip repository prefixes and expand omitted target names into canonical nodes. [strip_repository_qualifiers, expand_omitted_target_names, bazel_target: [normalize_identifier_to_node]]
- Extracting a node directory translates package coordinates into a relative directory path anchored to the workspace root. [derive_node_directories_relative_to_root, bazel_target: [extract_node_dir_from_node]]

## Grounding

### Knowledge Provisions

- Canonical Bazel target label normalization and workspace package directory derivation. [bazel_target_resolution]

### Inherited Deferred Requirements

- Parsing and normalization of arbitrary Bazel target label formats into canonical nodes.
  - Grounded: [bazel_target_labels_ext: [bazel_target_label_parsing]]
- Translation of canonical package identifiers into workspace-relative paths.
  - Grounded: [bazel_target_labels_ext: [bazel_package_directory_resolution], file_paths: [path_resolution_service]]

### Knowledge Requirements

- Validation and normalization of target label strings.
  - Grounded: [bazel_target_labels_ext: [bazel_target_label_parsing]]
- Relative package directory extraction anchored to the workspace root.
  - Grounded: [bazel_target_labels_ext: [bazel_package_directory_resolution], file_paths: [path_resolution_service]]
