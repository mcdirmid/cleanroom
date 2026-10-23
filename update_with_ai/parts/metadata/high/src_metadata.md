# src_metadata interface component

## Purpose

The src_metadata interface component defines data types and operational contracts for parsing, hashing, and mutating in-band source file metadata blocks.

Storing dirty tracking status, code hashes, audit timestamps, and diagnostic feedback directly inside source files enables decentralized build state without external database engines. Without a unified metadata interface, different control and storage components risk inconsistent comment handling, uncoordinated timestamp mutation, and corrupting file bodies during header updates. The src_metadata interface component establishes standard data types for extracted file metadata and defines capabilities for calculating code body hashes, evaluating modifications, and rewriting comment headers in-place.

**Out of scope:** The src_metadata interface component does not schedule task queues, execute language model reasoning loops, or resolve build graph dependencies; these are handled by other components.

## Types and Behavior

A *file metadata* record encapsulates in-band metadata attributes: a *last cleaned timestamp* when clean, a *last changed timestamp* when modified, a *change summary*, unacted *feedback items*, role *audit timestamps*, a *dirty reason* when dirtiness is attributed, and a *code hash* when computed.

The system's *source metadata coordinator* parses, computes, and mutates in-band file metadata.

The source metadata coordinator extracts file metadata from source content strings and workspace files, and extracts the *code body* of a source file by isolating the file content outside its metadata comment headers.

The source metadata coordinator computes a deterministic code hash over the code body, and evaluates whether a file has code modifications by comparing its on-disk code hash with its recorded in-band code hash.

The source metadata coordinator evaluates whether proposed content changes alter, corrupt, delete, or inject in-band cleanroom metadata blocks relative to original content strings.

The source metadata coordinator rewrites metadata comment blocks in content strings and updates files on disk in place. In-band metadata blocks adhere to format-specific commenting conventions positioned at the bottom of the file following source content to preserve code line numbers: Python source files (`.py`, `.pyi`) format metadata as line comments delimited by `# --- CLEANROOM METADATA ---` and `# --- END CLEANROOM METADATA ---` appended at the end of the file; Markdown specifications (`.md`) format metadata as HTML comments delimited by `<!-- CLEANROOM METADATA` and `-->` appended at the end of the document. When extracting metadata, the coordinator detects comment blocks positioned at the bottom or anywhere within the file.

The source metadata coordinator updates lifecycle status by marking files clean, marking files dirty, recording change summaries, appending unacted feedback items, stamping role audits, clearing role audits, and deleting last cleaned timestamps.

The component also exposes module-level procedural facade functions for metadata extraction, code body isolation, code hashing, modification checks, metadata alteration checks, and lifecycle updates, delegating each operation to the active source metadata coordinator singleton, alongside utilities for role audit tagging, auditor role classification, metadata parsing and formatting, and UTC timestamp generation.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-20T22:32:00Z
CHANGE: Contract metadata alteration detection capability on SourceMetadataCoordinator and module facade
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
