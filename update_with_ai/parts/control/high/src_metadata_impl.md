<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T14:35:00Z
CHANGE: new file
CODE_HASH: 7f93c7502b08
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

A session's *source metadata coordinator* realizes source file metadata operations as a session service.

The source metadata coordinator:

- Locates comment block boundaries by detecting HTML comment markers in Markdown specifications or line hash comment markers in Python, Starlark, and shell files.

- Parses in-band fields by extracting `LAST_CLEANED`, `LAST_CHANGED`, `CHANGE`, `CODE_HASH`, `DIRTY`, `<ROLE>_AUDIT`, and unacted `FEEDBACK` lines from comment block slices into file metadata records.

- Extracts code bodies by concatenating file lines preceding and following metadata comment boundaries, stripping whitespace.

- Computes deterministic code hashes by calculating the first twelve hexadecimal characters of the SHA-256 digest of the extracted code body.

- Evaluates code modification status by checking file existence on disk, extracting in-band metadata, and comparing current code hash against recorded code hash values.

- Rewrites metadata in text strings by replacing existing comment block slices or inserting new blocks below shebangs, encoding directives, or markdown frontmatter delimiters.

- Mutates source files in-place by reading content, computing updated comment blocks, creating parent directories when absent, and writing UTF-8 encoded text.

- Updates node lifecycle state by advancing `LAST_CLEANED` to current UTC timestamp on mutations, setting `LAST_CHANGED` on changes, appending feedback entries, stamping role audits, and clearing dirty flags.
