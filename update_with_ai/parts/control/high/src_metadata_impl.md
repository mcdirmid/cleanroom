<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-06T14:35:00Z
CHANGE: new file
CODE_HASH: 388be24fc26a
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# src_metadata_impl implementation component

imports: agent_session, src_metadata_ext
implements: src_metadata

## Purpose

The src_metadata_impl implementation component realizes in-band metadata parsing, deterministic code hashing, and in-place source header rewriting.

Direct filesystem mutations and regex parsing require concrete execution semantics to guarantee lossless updates across diverse source file structures. Storing dirty tracking state and feedback records directly inside source files requires precise line indexing to preserve shebang directives, encoding declarations, and markdown frontmatter while updating in-band metadata headers. The src_metadata_impl implementation component provides concrete algorithms for comment boundary extraction, field parsing, SHA-256 code hashing, and in-place document serialization.

**Out of scope:** The src_metadata_impl implementation component does not schedule task queues, execute language model reasoning loops, or resolve build graph dependencies; these are handled by other components.

**Delegated:** File format comment delimiters, header placement rules, and metadata grammar syntax are delegated to src_metadata_ext.

## Types and Behavior

An agent session's *source metadata coordinator* realizes source file metadata operations as a session service.

The source metadata coordinator locates comment block boundaries by detecting HTML comment markers in Markdown specifications or line hash comment markers in Python, Starlark, and shell files, and parses the in-band fields from a comment block slice into a file metadata record.

The source metadata coordinator extracts the code body by concatenating the file lines preceding and following the metadata comment boundaries with whitespace stripped, and computes the deterministic code hash as the first twelve hexadecimal characters of the SHA-256 digest of that code body.

The source metadata coordinator evaluates code modification status by establishing file existence on disk, extracting the in-band metadata, and comparing the current code hash against the recorded code hash.

The source metadata coordinator rewrites metadata in a text string by replacing an existing comment block slice or inserting a new block below a shebang, an encoding directive, or a markdown frontmatter delimiter.

The source metadata coordinator mutates a source file in place by reading its content, computing the updated comment block, creating parent directories when absent, and writing UTF-8 encoded text.

The source metadata coordinator updates node lifecycle state by advancing the last cleaned timestamp to the current UTC timestamp on mutation, setting the last changed timestamp on change, appending feedback entries, stamping role audits, and clearing the dirty reason.
