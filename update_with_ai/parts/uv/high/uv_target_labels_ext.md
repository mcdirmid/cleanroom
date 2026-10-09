<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: edf7d9f0ea51
-->

# uv_target_labels_ext external component

## Purpose

The uv_target_labels_ext external component normalizes target identifier strings into canonical syntax and resolves package filesystem directories.

Cleanroom targets can be addressed using package-qualified labels, colon syntax, filesystem paths, or shorthand syntax with optional role qualifiers. Inconsistent target representations cause duplicate graph nodes and broken lookups if compared as raw strings. The uv_target_labels_ext external component defines the external boundary for normalizing diverse target identifier formats into canonical package and unit coordinates with optional role specifiers, and resolving package directories against a workspace root.

**Out of scope:** The uv_target_labels_ext external component does not resolve build dependencies, inspect disk contents, or track message queues; these are handled by other components.

## Grounding Gaps Covered

The uv_target_labels_ext component provides external domain knowledge and parsing rules required to process Cleanroom target labels and map packages to filesystem locations.

Grounding gaps covered include:

- Target label normalization: Parses diverse target label representations including package-qualified labels, leading double-slash qualifiers, shorthand unit names, filesystem paths, and role-annotated target strings, expanding implicit target identifiers into canonical package and unit format with optional role addresses.

- Package filesystem directory resolution: Translates canonical package identifiers into relative filesystem directory paths, resolves package directory paths against physical workspace root directories, and correctly handles workspace root package targets.

- Target syntax validation: Enforces Cleanroom label character set rules and syntax constraints, validating package path segments and unit names while rejecting malformed or ambiguous label strings.
