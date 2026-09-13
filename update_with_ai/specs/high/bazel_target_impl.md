# bazel_target_impl implementation component

imports: dag_storage, file_paths, bazel_target_labels_ext
implements: bazel_target

## Purpose

The bazel_target_impl implementation component realizes Bazel label canonicalization, omitted target name expansion, and workspace directory extraction.

Bazel targets can be addressed using apparent, repository-qualified, or shorthand syntax, creating potential node duplication and broken package lookups. The bazel_target_impl implementation component strips repository prefixes, infers implicit target basenames, and resolves package directory locations against the workspace root.

**Out of scope:** The bazel_target_impl implementation component does not parse protobuf records, track message queues, or configure agent sandboxes; these are handled by other components.

## Types and Behavior

The bazel target normalizes raw target labels into canonical nodes by stripping repository qualifiers and expanding omitted target names.

The bazel target derives node directories from normalized nodes by extracting package directory paths relative to a workspace root.
