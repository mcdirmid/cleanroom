<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T14:35:00Z
CHANGE: new file
CODE_HASH: 1ddabf45adbe
-->

# src_metadata interface component

imports: agent_session, src_metadata_ext

## Intent

The src_metadata interface component defines data types and operational contracts for extracting, evaluating, and mutating in-band source file metadata blocks.

Decentralized dirty tracking and feedback distribution require uniform metadata manipulation across heterogeneous source formats. The source metadata coordinator acts as the authoritative interface for parsing comment headers, computing deterministic code hashes, checking code modifications, and applying in-place metadata updates without corrupting underlying source code bodies.

## Factored Contracts

### Typing

- A file metadata record encapsulates an optional last cleaned timestamp, an optional last changed timestamp, a change summary, a feedback list, an audits mapping, an optional dirty reason, and an optional code hash.
- A source metadata coordinator operates within the agent session lifecycle tier.

### Contracts

- A source metadata coordinator extracts file metadata from source content strings. [extract_metadata_content]
- A source metadata coordinator extracts file metadata from files on disk. [extract_metadata_disk]
- A source metadata coordinator extracts a source code body by isolating content outside metadata headers. [extract_code_body_content]
- A source metadata coordinator computes a deterministic twelve-character digest of a code body. [compute_code_hash_value]
- A source metadata coordinator evaluates code modifications by comparing disk hash against in-band hash. [evaluate_code_modified]
- A source metadata coordinator rewrites comment headers within content strings. [rewrite_metadata_text]
- A source metadata coordinator applies in-place comment block modifications to files on disk. [update_metadata_disk]
- A source metadata coordinator marks files clean by updating last cleaned timestamp while clearing feedback. [mark_clean_status]
- A source metadata coordinator marks files dirty by setting dirty reason while updating last cleaned timestamp. [mark_dirty_status]
- A source metadata coordinator records change descriptions while updating change summary with new code hash. [record_change_status]
- A source metadata coordinator appends unacted feedback entries while advancing last cleaned timestamp. [append_feedback_entry]
- A source metadata coordinator stamps role audits with current UTC timestamp while advancing last cleaned timestamp. [stamp_audit_entry]
- A source metadata coordinator clears all role audit entries from file metadata. [clear_audits_entries]
- A source metadata coordinator deletes last cleaned timestamps from file metadata. [delete_last_cleaned_entry]

### Woven Contracts

- When evaluating whether a file has modifications, the coordinator extracts on-disk metadata and compares computed code hash against recorded code hash. [extract_metadata_disk, compute_code_hash_value, evaluate_code_modified]
- When marking a file clean, the coordinator advances last cleaned timestamp to now, preserves or initializes last changed timestamp, and clears unacted feedback. [mark_clean_status, update_metadata_disk]
- When recording a change, the coordinator updates last cleaned timestamp, sets last changed timestamp to now, updates change summary, stamps new code hash, and clears unacted feedback. [record_change_status, compute_code_hash_value, update_metadata_disk]

## Grounding

### Knowledge Provisions

- Metadata extraction, hashing, modification check, and in-place rewriting capabilities. [source_metadata_service]
- In-band header field extraction, block placement, and UTF-8 disk mutation mechanics. [source_metadata_manipulation]

### Knowledge Requirements

- Parsing of multi-format comments and serialization of in-band metadata comment blocks.
  - Deferred: Provided by source metadata coordinator implementation.
- Hashing of source code bodies excluding metadata headers.
  - Deferred: Provided by source metadata coordinator implementation.
- In-place mutation of workspace source files.
  - Deferred: Provided by source metadata coordinator implementation.
