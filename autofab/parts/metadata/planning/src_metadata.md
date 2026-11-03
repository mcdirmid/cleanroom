# src_metadata interface component

## Intent

The src_metadata interface component defines data types and operational contracts for extracting, evaluating, and mutating in-band source file metadata blocks.

Decentralized dirty tracking and feedback distribution require uniform metadata manipulation across heterogeneous source formats. The source metadata coordinator acts as the authoritative interface for parsing comment headers, computing deterministic code hashes, checking code modifications, and applying in-place metadata updates without corrupting underlying source code bodies.

## Factored Contracts

### Typing

- A file metadata record encapsulates a last cleaned timestamp when clean, a last changed timestamp when modified, a change summary, unacted feedback items, role audit timestamps, a dirty reason when dirtiness is attributed, and a code hash when computed.
- A source metadata coordinator operates within the system lifecycle tier.
- In-band metadata blocks format Python metadata as line comments delimited by `# --- CLEANROOM METADATA ---` and `# --- END CLEANROOM METADATA ---` positioned at the bottom of files, and Markdown metadata as HTML comments delimited by `<!-- CLEANROOM METADATA` and `-->` positioned at the bottom of documents.
- Module-level procedural facade functions delegate operations directly to the active source metadata coordinator singleton.

### Contracts

- A source metadata coordinator extracts file metadata from source content strings. [extract_metadata_content]
- A source metadata coordinator extracts file metadata from files on disk. [extract_metadata_disk]
- A source metadata coordinator extracts a source code body by isolating content outside metadata headers. [extract_code_body_content]
- A source metadata coordinator computes a deterministic twelve-character digest of a code body. [compute_code_hash_value]
- A source metadata coordinator evaluates code modifications by comparing disk hash against in-band hash. [evaluate_code_modified]
- A source metadata coordinator evaluates whether proposed content changes alter, corrupt, delete, or inject in-band metadata comment blocks. [evaluate_metadata_altered]
- A source metadata coordinator rewrites comment blocks within content strings, positioning updated blocks at the bottom of the file. [rewrite_metadata_text]
- A source metadata coordinator applies in-place comment block modifications to files on disk. [update_metadata_disk]
- A source metadata coordinator marks files clean by updating last cleaned timestamp while clearing feedback. [mark_clean_status]
- A source metadata coordinator marks files dirty by setting dirty reason while updating last cleaned timestamp. [mark_dirty_status]
- A source metadata coordinator records change descriptions while updating change summary with new code hash. [record_change_status]
- A source metadata coordinator appends unacted feedback entries while advancing last cleaned timestamp. [append_feedback_entry]
- A source metadata coordinator stamps role audits with current UTC timestamp while advancing last cleaned timestamp. [stamp_audit_entry]
- A source metadata coordinator clears all role audit entries from file metadata. [clear_audits_entries]
- A source metadata coordinator deletes last cleaned timestamps from file metadata. [delete_last_cleaned_entry]
- Module-level procedural facade functions delegate metadata queries and mutations to the coordinator singleton, alongside utilities for role audit tagging, auditor role classification, metadata parsing and formatting, and UTC timestamp generation. [delegate_procedural_facades]

### Woven Contracts

- When evaluating whether a file has modifications, the coordinator extracts on-disk metadata and compares computed code hash against recorded code hash. [extract_metadata_disk, compute_code_hash_value, evaluate_code_modified]
- When checking if metadata is altered, the coordinator evaluates comment block boundaries and content equality between original and new content strings. [evaluate_metadata_altered]
- When marking a file clean, the coordinator advances last cleaned timestamp to now, preserves or initializes last changed timestamp, and clears unacted feedback. [mark_clean_status, update_metadata_disk]
- When recording a change, the coordinator updates last cleaned timestamp, sets last changed timestamp to now, updates change summary, stamps new code hash, and clears unacted feedback. [record_change_status, compute_code_hash_value, update_metadata_disk]
- Calling a module-level procedural facade function resolves the active coordinator singleton and forwards invocation arguments. [delegate_procedural_facades]

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

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-20T22:32:00Z
CHANGE: Plan metadata alteration evaluation contract on SourceMetadataCoordinator
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
