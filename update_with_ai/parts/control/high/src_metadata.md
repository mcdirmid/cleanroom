<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-06T14:35:00Z
CHANGE: new file
CODE_HASH: 393fd04c7151
SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
-->

# src_metadata interface component

imports: agent_session

## Purpose

The src_metadata interface component defines data types and operational contracts for parsing, hashing, and mutating in-band source file metadata blocks.

Storing dirty tracking status, code hashes, audit timestamps, and diagnostic feedback directly inside source files enables decentralized build state without external database engines. Without a unified metadata interface, different control and storage components risk inconsistent comment handling, uncoordinated timestamp mutation, and corrupting file bodies during header updates. The src_metadata interface component establishes standard data types for extracted file metadata and defines capabilities for calculating code body hashes, evaluating modifications, and rewriting comment headers in-place.

**Out of scope:** The src_metadata interface component does not schedule task queues, execute language model reasoning loops, or resolve build graph dependencies; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *file metadata* record encapsulates in-band metadata attributes: a *last cleaned timestamp* when clean, a *last changed timestamp* when modified, a *change summary*, unacted *feedback items*, role *audit timestamps*, a *dirty reason* when dirtiness is attributed, and a *code hash* when computed.

An agent session's *source metadata coordinator* parses, computes, and mutates in-band file metadata.

The source metadata coordinator extracts file metadata from source content strings and workspace files, and extracts the *code body* of a source file by isolating the file content outside its metadata comment headers.

The source metadata coordinator computes a deterministic code hash over the code body, and evaluates whether a file has code modifications by comparing its on-disk code hash with its recorded in-band code hash.

The source metadata coordinator rewrites metadata comment headers in content strings and updates files on disk in place.

The source metadata coordinator updates lifecycle status by marking files clean, marking files dirty, recording change summaries, appending unacted feedback items, stamping role audits, clearing role audits, and deleting last cleaned timestamps.
