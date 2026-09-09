# bazel_node_id_utils_impl implementation component

imports: dag_storage, file_alias, bazel_target_labels_ext
implements: bazel_node_id_utils

## Purpose

The bazel_node_id_utils_impl implementation component realizes Bazel label canonicalization, omitted target name expansion, and workspace directory extraction.

Bazel targets can be addressed using apparent, repository-qualified, or shorthand syntax, creating potential node duplication and broken package lookups. The bazel_node_id_utils_impl implementation component strips repository prefixes, infers implicit target basenames, and resolves package directory locations against the workspace root.

**Out of scope:** The bazel_node_id_utils_impl implementation component does not parse protobuf records, track message queues, or configure agent sandboxes; these are handled by other components.

## Types and Behavior

The bazel node identifier utility normalizes raw target labels from bazel target labels ext into canonical nodes in dag storage by stripping repository qualifiers and expanding omitted target names.

The bazel node identifier utility derives node directories from normalized nodes by extracting package directory paths relative to a workspace root from file alias.
