<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: a66b4b9108b6
SPEC_QA_AUDIT: 2026-10-07T23:58:18Z
-->

# uv_target_impl implementation component

imports: dag_storage, file_paths, uv_target_labels_ext
implements: uv_target

## Intent

Targets can be addressed using apparent paths, repository qualifiers, or shorthand colon syntax, creating potential node duplication and broken package lookups. Addressing targets inconsistently leads to duplicate sessions and orphaned change records. The uv_target_impl implementation component strips repository prefixes, infers implicit target basenames, and resolves package directory locations against the workspace root.

By delegating label normalization and package resolution to the uv_target_labels_ext external boundary, the implementation produces canonical dag nodes and reliable workspace directory mappings.

## Factored Contracts

### Contracts

- The uv target strips repository qualifiers when normalizing raw target labels. [strip_repository_qualifiers]
- The uv target expands omitted target names when normalizing raw target labels. [expand_omitted_target_names]
- The uv target derives node directories by extracting package directory paths relative to a workspace root. [derive_node_directories_relative_to_root]

### Woven Contracts

- Normalizing target labels invokes external label parsing to strip repository prefixes and expand omitted target names into canonical nodes. [strip_repository_qualifiers, expand_omitted_target_names, uv_target: [normalize_identifier_to_node]]
- Extracting a node directory translates package coordinates into a relative directory path anchored to the workspace root. [derive_node_directories_relative_to_root, uv_target: [extract_node_dir_from_node]]

## Grounding

### Knowledge Provisions

- Canonical target label normalization and workspace package directory derivation. [uv_target_resolution]

### Inherited Deferred Requirements

- Parsing and normalization of arbitrary target label formats into canonical nodes.
  - Grounded: [uv_target_labels_ext: [uv_target_label_parsing]]
- Translation of canonical package identifiers into workspace-relative paths.
  - Grounded: [uv_target_labels_ext: [uv_package_directory_resolution], file_paths: [path_resolution_service]]

### Knowledge Requirements

- Validation and normalization of target label strings.
  - Grounded: [uv_target_labels_ext: [uv_target_label_parsing]]
- Relative package directory extraction anchored to the workspace root.
  - Grounded: [uv_target_labels_ext: [uv_package_directory_resolution], file_paths: [path_resolution_service]]
