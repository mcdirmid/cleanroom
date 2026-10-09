<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: ea80dd2346df
-->

# uv_target_impl implementation component

imports: dag_storage, file_paths, uv_target_labels_ext
implements: uv_target

## Purpose

The uv_target_impl implementation component realizes target label canonicalization, omitted target name expansion, and workspace directory extraction.

Targets can be addressed using apparent paths, repository qualifiers, or shorthand colon syntax, creating potential node duplication and broken package lookups. Addressing targets inconsistently leads to duplicate sessions and orphaned change records. The uv_target_impl implementation component strips repository prefixes, infers implicit target basenames, and resolves package directory locations against the workspace root.

**Out of scope:** The uv_target_impl implementation component does not parse protobuf records, track message queues, or configure agent sandboxes; these are handled by other components.

**Delegated:** Label syntax normalization and package resolution rules are delegated to uv_target_labels_ext; workspace path representation is delegated to file_paths; graph node referencing is delegated to dag_storage.

## Types and Behavior

The uv target normalizes raw target labels into canonical nodes by stripping repository qualifiers and expanding omitted target names.

The uv target derives node directories from normalized nodes by extracting package directory paths relative to a workspace root.
