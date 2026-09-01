# bazel_target_labels_ext

## Purpose

Normalizes raw Bazel target labels into canonical syntax and resolves package filesystem directories, ensuring consistent dependency addressing across repository boundaries.

Bazel targets can be addressed using apparent, repository-qualified, or shorthand label syntax, causing duplicate graph nodes and broken lookups if compared as raw strings. Bazel target labels normalization converts diverse label formats into canonical package-and-target forms (`//pkg:target`) and resolves target package directories against a workspace root, guaranteeing deterministic target resolution across the build.

## Types

- A *raw target label* is a target identifier in any valid Bazel syntax form
- A *canonical target label* is a normalized Bazel target label identifying a package and target
- A *package directory* is a filesystem directory path corresponding to a target package

## Behavior

- A *raw target label* can be normalized into a *canonical target label*.
- Normalizing a *raw target label* strips main-repository qualifiers and expands omitted target names.
- A *canonical target label* uniquely addresses a target within the workspace.
- A *package directory* can be extracted from a *canonical target label* relative to a workspace root.
