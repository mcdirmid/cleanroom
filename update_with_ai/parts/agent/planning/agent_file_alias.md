<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:00:56Z
CHANGE: Align alias manager parameter conversion typing with the high-level contract and drop planning front-matter
CODE_HASH: b9d477c8ef32
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# agent_file_alias interface component

## Intent

Exposing raw operating system paths directly to language model agents invites hallucinated absolute paths, introduces cross-environment execution drift, and leaks local host directory structures into context windows. The agent_file_alias interface component creates an isolated virtual addressing space anchored to the active session, shielding the agent from underlying filesystem layouts while ensuring all referenced files correspond to tracked task boundaries and providing standard representations for file contents and search patterns.

By acting as a converter for tool parameters, the alias manager maps wire-level string arguments directly into bound or unbound file aliases, while masking absolute host prefixes from tool outputs to maintain context hygiene.

## Factored Contracts

### Typing

- File content represents data stored in a file.
- A regex pattern represents a pattern used to search in files.
- A file alias has a relative path identifying the file within an agent session.
- Converting a file alias to a string displays its relative path.
- A bound file is a file alias mapped to a workspace file with a workspace path.
- A bound file has an owning dag node.
- A read-only file is a bound file restricted to read access.
- A read-write file is a bound file permitted for read and write access.
- An unbound file is a file alias not mapped to an actual workspace file.
- The alias manager provides the to alias capability over file aliases, converting a path string to a file alias.

### Contracts

- A caller configures the alias manager with the absolute path of a workspace root. [configure_ws_root_path]
- A caller supplies a path string when resolving a file alias using the alias manager. [supply_path_string]
- A caller supplies text containing environment paths when requesting text sanitization. [supply_text_to_sanitize]
- The alias manager converts path strings to file aliases without failure. [to_alias_without_failure]
- Resolving a path string matching a declared bound file produces that read-only or read-write file. [to_alias_matching_bound_file]
- Resolving an unmatched path string produces an unbound file. [to_alias_unmatched_unbound_file]
- The alias manager sanitizes text by masking occurrences of relative workspace paths with file alias relative paths. [sanitize_mask_ws_paths]
- The alias manager sanitizes text by masking preceding path prefixes with file alias relative paths. [sanitize_mask_preceding_prefixes]

### Woven Contracts

- Resolving a string path produces a matching bound file if declared in session, or an unbound file otherwise without failure. [supply_path_string, to_alias_without_failure, to_alias_matching_bound_file, to_alias_unmatched_unbound_file]
- When sanitizing text, relative workspace paths and preceding path prefixes are masked to present file alias relative paths. [supply_text_to_sanitize, sanitize_mask_ws_paths, sanitize_mask_preceding_prefixes]

## Grounding

### Knowledge Provisions

- Virtual file alias mapping, conversion, and path sanitization for agent tool invocations. [alias_mapping]

### Knowledge Requirements

- Workspace root absolute path and session declared file boundaries.
  - Deferred: Configured from agent session and file paths in implementation.
