# bazel_target_impl implementation component

imports: dag_storage, file_paths, bazel_target_labels_ext
implements: bazel_target

## Assumptions and Requirements

### Requirements

1. The bazel target normalizes raw target labels by stripping repository qualifiers and expanding omitted target names.
2. The bazel target derives node directories from normalized nodes relative to a workspace root.

## Grounding Facts

### Knowledge Needed

- Raw target label syntax.
- Workspace root path.
- Node directory structure.

### Actions Needed

- Strip repository qualifiers and expand omitted target names via `bazel_target_labels_ext`.
- Derive node directory path relative to workspace root.
