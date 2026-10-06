# src_metadata_ext external component

## Intent

Direct coupling between build graph storage and heterogeneous source file formats introduces fragile syntax handling, comment corruption, and disparate header parsing routines across file types. Storing dirty tracking state and feedback records directly inside source files requires uniform recognition of comment delimiters, header placement rules, and lossless in-place document updates.

The src_metadata_ext external component provides external format definitions and comment manipulation mechanics for Markdown, Python, Python stubs, Starlark build rules, and shell scripts. By establishing a standardized external boundary for embedded metadata blocks, storage implementations interact with file headers through a uniform interface without risking syntax corruption or losing source code integrity.

## Grounding

### Knowledge Provisions

- In-band comment metadata parsing and lossless in-place header rewriting across source formats. [src_metadata_operations]
