# metadata_asm assembly component

assembles: src_metadata_impl, src_storage_impl
imports: session, file_paths, src_metadata_ext
implements: node_storage, dag_storage, src_metadata

## Purpose

The metadata_asm assembly component aggregates in-band source file metadata management and persistent graph storage implementations into the unified storage package.

Cleanroom builds and multi-agent coordination loops require durable, in-band persistence of source file metadata, code hashes, audit records, and topological graph indexing without external databases. The metadata_asm assembly component initializes constituent services and registers singleton implementations with the system and agent session lifecycle registries.

**Out of scope:** The metadata_asm assembly component does not implement individual parsing or graph indexing logic, execute verification checks, or run language model reasoning loops; these are handled by other components.

## Types and Behavior

The metadata_asm assembly component aggregates the implementations of the source metadata coordinator, agent storage, and DAG storage interfaces, providing a unified assembly for in-band metadata manipulation and target storage.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:57Z
LAST_CHANGED: 2026-10-14T17:25:00Z
CHANGE: Define metadata_asm assembly component
SPEC_QA_AUDIT: 2026-10-15T19:43:57Z
-->
