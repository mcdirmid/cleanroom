<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T14:35:00Z
CHANGE: new file
CODE_HASH: 903e1ab0f625
-->

# src_metadata_ext external component

## Purpose

The src_metadata_ext external component defines external comment syntax conventions, header boundaries, and field grammar for in-band source file metadata blocks.

Direct coupling between build graph storage and heterogeneous source file formats introduces fragile syntax handling, comment corruption, and disparate header parsing routines across file types. Storing dirty tracking state and feedback records directly inside source files requires uniform recognition of comment delimiters, header placement rules, and lossless in-place document updates. The src_metadata_ext external component provides external format definitions and comment manipulation mechanics for Markdown, Python, Python stubs, Starlark build rules, and shell scripts, ensuring that storage implementations interact with embedded file headers through a standardized boundary.

**Out of scope:** The src_metadata_ext external component does not evaluate target dependencies, resolve file paths, or execute agent cleaning loops; these are handled by other components.

## Grounding Gaps Covered

The src_metadata_ext component provides external schema knowledge and serialization mechanics for reading and updating in-band metadata comment blocks across Cleanroom file formats.

Grounding gaps covered include:

- Multi-format comment syntax identification: Identifies file type comment delimiters, parsing HTML comment blocks for Markdown specifications and line hash comment blocks for Python source files, Python stubs, Starlark build files, and shell scripts.

- Header placement and boundary extraction: Locates metadata comment blocks positioned at the beginning of files, placing blocks below initial shebang directives or encoding lines in executable scripts, placing blocks after YAML frontmatter delimiters in Markdown specifications, and isolating metadata content from surrounding source code.

- In-band metadata grammar parsing: Parses structured metadata fields from comment content, extracting UTC ISO 8601 timestamps for last cleaned and last changed attributes, extracting single-line change descriptions, code hash signatures, dirty status flags, role audit timestamps, and parsing conditional unacted feedback lists carrying timestamp, source node, and diagnostic explanation attributes.

- In-place metadata block rewriting: Rewrites source files in-place with updated timestamps, revised change descriptions, cleared last cleaned timestamps, appended unacted feedback entries, role audit stamps, or stripped feedback sections, preserving exact source code content, shebang headers, and frontmatter formatting below the comment header.
