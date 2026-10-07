<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T14:35:00Z
CHANGE: new file
CODE_HASH: 694ef71ee416
-->

# src_metadata_ext external component

## Intent

Direct coupling between build graph storage and heterogeneous source file formats introduces fragile syntax handling, comment corruption, and disparate header parsing routines across file types. Storing dirty tracking state and feedback records directly inside source files requires uniform recognition of comment delimiters, header placement rules, and lossless in-place document updates.

The src_metadata_ext external component provides external format definitions and comment manipulation mechanics for Markdown, Python, Python stubs, Starlark build rules, and shell scripts. By establishing a standardized external boundary for embedded metadata blocks, storage implementations interact with file headers through a uniform interface without risking syntax corruption or losing source code integrity.

## Grounding

### Knowledge Provisions

- In-band comment metadata parsing and lossless in-place header rewriting across source formats. [src_metadata_operations]
- Multi-format comment delimiters, placement rules, and metadata field grammar. [src_metadata_format_grammar]
