<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-05T04:26:30Z
CHANGE: new file
CODE_HASH: 15ca95dc3a0e
-->

# src_metadata_ext external component

## Intent

Direct coupling between build graph storage and heterogeneous source file formats introduces fragile syntax handling, comment corruption, and disparate header parsing routines across file types. Storing dirty tracking state and feedback records directly inside source files requires uniform recognition of comment delimiters, header placement rules, and lossless in-place document updates.

The src_metadata_ext external component provides external format definitions and comment manipulation mechanics for Markdown, Python, Python stubs, Starlark build rules, and shell scripts. By establishing a standardized external boundary for embedded metadata blocks, storage implementations interact with file headers through a uniform interface without risking syntax corruption or losing source code integrity.

## Factored Contracts

### Contracts

- A caller supplies a filesystem path when extracting metadata. [extract_path_supplied]
- A caller supplies file text when parsing in-band metadata. [parse_text_supplied]
- A caller supplies metadata attributes when updating source file headers. [update_attributes_supplied]
- Markdown specifications delimit metadata using HTML comment syntax. [markdown_html_delimiters]
- Python source files delimit metadata using line hash comment syntax. [python_hash_delimiters]
- Python interface stubs delimit metadata using line hash comment syntax. [stub_hash_delimiters]
- Starlark build files delimit metadata using line hash comment syntax. [starlark_hash_delimiters]
- Shell scripts delimit metadata using line hash comment syntax. [shell_hash_delimiters]
- Metadata blocks in executable scripts reside below shebang directives. [shebang_placement_order]
- Metadata blocks in executable scripts reside below encoding declarations. [encoding_placement_order]
- Metadata blocks in Markdown specifications reside below frontmatter delimiters. [frontmatter_placement_order]
- Metadata parsing extracts UTC ISO 8601 timestamps for last cleaned timestamps. [parse_last_cleaned_timestamp]
- Metadata parsing extracts UTC ISO 8601 timestamps for last changed timestamps. [parse_last_changed_timestamp]
- Metadata parsing extracts a single-line change description. [parse_change_description]
- Metadata parsing extracts a list of unacted feedback entries. [parse_unacted_feedback_list]
- In-place rewriting updates the last cleaned timestamp. [rewrite_last_cleaned_timestamp]
- In-place rewriting clears the last cleaned timestamp when marking dirty. [rewrite_clear_last_cleaned]
- In-place rewriting updates the last changed timestamp. [rewrite_last_changed_timestamp]
- In-place rewriting replaces the change description. [rewrite_change_description]
- In-place rewriting appends unacted feedback entries. [rewrite_append_feedback]
- In-place rewriting removes the feedback section upon clean. [rewrite_remove_feedback]
- In-place rewriting preserves source file content outside the metadata header. [rewrite_preserve_body]

## Woven Contracts

- When extracting metadata from a file path, the file format determines whether HTML comment syntax or line hash comment syntax is parsed. [extract_path_supplied, parse_text_supplied, markdown_html_delimiters, python_hash_delimiters, stub_hash_delimiters, starlark_hash_delimiters, shell_hash_delimiters]
- When parsing header blocks in scripts or Markdown documents, metadata boundaries are located below shebang directives, encoding lines, or frontmatter delimiters. [shebang_placement_order, encoding_placement_order, frontmatter_placement_order]
- When parsing in-band metadata, timestamps, change descriptions, and unacted feedback lists are decoded into structured metadata attributes. [parse_last_cleaned_timestamp, parse_last_changed_timestamp, parse_change_description, parse_unacted_feedback_list]
- When updating source files in-place, the header is updated with timestamps, change descriptions, and feedback modifications while preserving the remaining file content unchanged. [update_attributes_supplied, rewrite_last_cleaned_timestamp, rewrite_clear_last_cleaned, rewrite_last_changed_timestamp, rewrite_change_description, rewrite_append_feedback, rewrite_remove_feedback, rewrite_preserve_body]
