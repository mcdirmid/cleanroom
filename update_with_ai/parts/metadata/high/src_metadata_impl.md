# src_metadata_impl implementation component

imports: src_metadata_ext
implements: src_metadata

## Purpose

The src_metadata_impl implementation component realizes in-band metadata parsing, deterministic code hashing, and in-place source header rewriting.

Direct filesystem mutations and regex parsing require concrete execution semantics to guarantee lossless updates across diverse source file structures. Storing dirty tracking state and feedback records directly inside source files requires appending metadata blocks at the bottom of files to preserve line numbers, preventing drift in compiler errors, test tracebacks, and coverage diagnostics. The src_metadata_impl implementation component provides concrete algorithms for comment boundary extraction, field parsing, SHA-256 code hashing, and in-place document serialization.

**Out of scope:** The src_metadata_impl implementation component does not schedule task queues, execute language model reasoning loops, or resolve build graph dependencies; these are handled by other components.

**Delegated:** File format comment delimiters, comment block placement rules, and metadata grammar syntax are delegated to src_metadata_ext.

## Types and Behavior

The system's *source metadata coordinator* realizes source file metadata operations as a system service.

The source metadata coordinator locates comment block boundaries by detecting HTML comment markers in Markdown specifications or line hash comment markers in Python, Starlark, and shell files, and parses the in-band fields from a comment block slice into a file metadata record.

The source metadata coordinator extracts the code body by concatenating the file lines preceding and following the metadata comment boundaries with whitespace stripped, and computes the deterministic code hash as the first twelve hexadecimal characters of the SHA-256 digest of that code body.

The source metadata coordinator evaluates code modification status by establishing file existence on disk, extracting the in-band metadata, and comparing the current code hash against the recorded code hash.

The source metadata coordinator rewrites metadata in a text string by removing any existing metadata comment block and appending the updated block at the bottom of the content string separated by a newline.

The source metadata coordinator mutates a source file in place by reading its content, computing the updated comment block, creating parent directories when absent, and writing UTF-8 encoded text.

The source metadata coordinator updates node lifecycle state by advancing the last cleaned timestamp to the current UTC timestamp on mutation, setting the last changed timestamp on change, appending feedback entries, stamping role audits, and clearing the dirty reason.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-06T14:35:00Z
CHANGE: new file
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
