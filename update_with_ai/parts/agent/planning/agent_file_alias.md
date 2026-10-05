<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:28:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 93db2f820f46
-->

# agent_file_alias interface component

imports: agent_session, dag_storage, file_paths, tool_provider

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
- The alias manager is a parameter type with python type file alias and wire type string.

### Contracts

- A caller configures the alias manager with the absolute path of a workspace root. [configure_ws_root_path]
- A caller supplies a wire type string when converting arguments using the alias manager. [supply_wire_alias_string]
- A caller supplies text containing environment paths when requesting text sanitization. [supply_text_to_sanitize]
- The alias manager converts wire type strings to file aliases without failure. [convert_alias_without_failure]
- Converting a wire type string matching a declared bound file produces that read-only or read-write file. [convert_matching_bound_file]
- Converting an unmatched wire type string produces an unbound file. [convert_unmatched_unbound_file]
- The alias manager sanitizes text by masking occurrences of relative workspace paths with file alias relative paths. [sanitize_mask_ws_paths]
- The alias manager sanitizes text by masking preceding path prefixes with file alias relative paths. [sanitize_mask_preceding_prefixes]

## Woven Contracts

- Converting a wire string produces a matching bound file if declared in session, or an unbound file otherwise without failure. \[supply_wire_alias_string, convert_alias_without_failure, convert_matching_bound_file, convert_unmatched_unbound_file, tool_provider: [convert_wire_val, convert_identity]\]
- When sanitizing text, relative workspace paths and preceding path prefixes are masked to present file alias relative paths. [supply_text_to_sanitize, sanitize_mask_ws_paths, sanitize_mask_preceding_prefixes]
