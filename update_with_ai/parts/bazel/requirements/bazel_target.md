# bazel_target interface component

imports: dag_storage, file_paths

## Assumptions and Requirements

### Requirements

1. The bazel target normalizes an arbitrary Bazel target identifier string into a canonical node.
2. The bazel target extracts a node directory from a node.

## Grounding Facts

### Knowledge Needed

- Bazel target identifier string.
- Target normalization syntax.
- Node package directory structure.

### Actions Needed

- Normalize Bazel target string into canonical node.
- Extract node directory from node.
