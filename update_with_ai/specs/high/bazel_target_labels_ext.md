# bazel_target_labels_ext external component

## Purpose

The bazel_target_labels_ext external component normalizes raw Bazel target labels into canonical syntax and resolves package filesystem directories.

Bazel targets can be addressed using apparent, repository-qualified, or shorthand label syntax, causing duplicate graph nodes and broken lookups if compared as raw strings. The bazel_target_labels_ext external component defines the external boundary for normalizing diverse Bazel label formats into canonical package and target coordinates and resolving package directories against a workspace root from file alias.

**Out of scope:** The bazel_target_labels_ext external component does not resolve build dependencies, inspect disk contents, or track message queues; these are handled by other components.

## Grounding Gaps Covered

The bazel_target_labels_ext component provides the external domain knowledge and parsing rules required to process Bazel target labels and map packages to filesystem locations:

- Bazel target label normalization: Parses diverse Bazel target label representations including fully qualified repository labels, main repository qualifiers, package-only shorthand where the target name matches the package name, and package-relative target names, stripping main repository prefixes and expanding implicit target identifiers into canonical `//package:target` format.

- Package filesystem directory resolution: Translates canonical package identifiers into relative filesystem directory paths, resolves package directory paths against physical workspace root directories, and correctly handles workspace root package targets.

- Target syntax validation: Enforces Bazel label character set rules and syntax constraints, validating package path segments and target names while rejecting malformed or ambiguous label strings.
