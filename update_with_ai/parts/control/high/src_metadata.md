<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T14:35:00Z
CHANGE: new file
CODE_HASH: 829cb477c297
-->

# src_metadata interface component

imports: agent_session, src_metadata_ext

## Purpose

The src_metadata interface component defines data types and operational contracts for parsing, hashing, and mutating in-band source file metadata blocks.

Storing dirty tracking status, code hashes, audit timestamps, and diagnostic feedback directly inside source files enables decentralized build state without external database engines. Without a unified metadata interface, different control and storage components risk inconsistent comment handling, uncoordinated timestamp mutation, and corrupting file bodies during header updates. The src_metadata interface component establishes standard data types for extracted file metadata and defines capabilities for calculating code body hashes, evaluating modifications, and rewriting comment headers in-place.

**Out of scope:** The src_metadata interface component does not schedule task queues, execute language model reasoning loops, or resolve build graph dependencies; these are handled by other components.

**Delegated:** File format comment delimiters, header placement rules, and metadata grammar syntax are delegated to src_metadata_ext.

## Types and Behavior

A *file metadata* record encapsulates in-band metadata attributes: an optional *last cleaned timestamp*, an optional *last changed timestamp*, a *change summary*, a *feedback list*, an *audits mapping*, an optional *dirty reason*, and an optional *code hash*.

A session's *source metadata coordinator* parses, computes, and mutates in-band file metadata.

The source metadata coordinator:

- Extracts file metadata from source content strings and workspace files.

- Extracts a source file's *code body* by isolating file content outside metadata comment headers.

- Computes a deterministic code hash over the code body.

- Evaluates whether a file has code modifications by comparing its on-disk code hash with its recorded in-band code hash.

- Rewrites metadata comment headers in content strings and updates files on disk in-place.

- Updates lifecycle status by marking files clean, marking files dirty, recording change descriptions, appending unacted feedback items, stamping role audits, clearing role audits, and deleting last cleaned timestamps.
