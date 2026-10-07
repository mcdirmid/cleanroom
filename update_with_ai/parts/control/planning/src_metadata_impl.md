<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T14:35:00Z
CHANGE: new file
CODE_HASH: fd8dd090f294
-->

# src_metadata_impl implementation component

imports: agent_session, src_metadata_ext
implements: src_metadata

## Intent

The src_metadata_impl implementation component provides concrete algorithms for multi-format comment boundary detection, structured key-value header parsing, SHA-256 code hashing, and in-place document serialization.

The implementation isolates comment delimiters according to file extensions, locates header boundaries skipping shebangs or frontmatter, computes truncated twelve-character digests of extracted code bodies, and updates or injects comment headers into source documents.

## Factored Contracts

### Contracts

- The source metadata coordinator identifies HTML comment blocks in Markdown files. [detect_html_delimiters]
- The source metadata coordinator identifies line hash comment blocks in code files. [detect_hash_delimiters]
- The source metadata coordinator parses metadata key-value lines into structured attributes. [parse_header_fields]
- The source metadata coordinator extracts body lines strictly outside comment block boundaries. [slice_code_body]
- The source metadata coordinator digests UTF-8 encoded code bodies using SHA-256. [digest_code_body]
- The source metadata coordinator compares current code digest against recorded code hash. [compare_code_digests]
- The source metadata coordinator formats file metadata records into comment lines. [format_header_lines]
- The source metadata coordinator locates header insertion positions below initial directives. [locate_insertion_index]
- The source metadata coordinator writes serialized content to disk with parent directory creation. [write_file_content]
- The source metadata coordinator advances last cleaned timestamp to current UTC time. [advance_cleaned_timestamp]

### Woven Contracts

- When extracting metadata from text or disk, the coordinator detects comment boundaries and parses header fields into a file metadata record. [detect_html_delimiters, detect_hash_delimiters, parse_header_fields, src_metadata: [extract_metadata_content, extract_metadata_disk]]
- When checking for code modifications, the coordinator extracts the code body, computes the SHA-256 digest, and compares the digest against the recorded code hash. [slice_code_body, digest_code_body, compare_code_digests, src_metadata: [compute_code_hash_value, evaluate_code_modified]]
- When rewriting or updating metadata, the coordinator formats the header lines, replaces or inserts the block, and writes the content to disk. [format_header_lines, locate_insertion_index, write_file_content, src_metadata: [rewrite_metadata_text, update_metadata_disk]]

## Grounding

### Knowledge Provisions

- Metadata extraction, hashing, modification check, and in-place rewriting capabilities. [source_metadata_service]
- In-band header field extraction, block placement, and UTF-8 disk mutation mechanics. [source_metadata_manipulation]

### Inherited Deferred Requirements

- Parsing of multi-format comments and serialization of in-band metadata comment blocks.
  - Grounded: [src_metadata_ext: [src_metadata_operations], src_metadata_ext: [src_metadata_format_grammar]]
- Hashing of source code bodies excluding metadata headers.
  - Grounded: [src_metadata_ext: [src_metadata_operations]]
- In-place mutation of workspace source files.
  - Grounded: [src_metadata_ext: [src_metadata_operations], source_metadata_manipulation]

### Knowledge Requirements

- Current UTC timestamp generation for metadata updates.
  - Grounded: [caller input, source_metadata_manipulation]
