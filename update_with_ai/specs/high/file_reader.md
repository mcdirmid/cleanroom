# file_reader

imports: tool_provider (tool results, tool failure, tool call)
terms (from tool_provider): tool result, tool failure, tool call, supersession flag
terms (owned): virtual name, line-numbered view, session-start read

## Purpose

Provides read-only file access and search across readable files: virtual-name addressing, full-content reading with plain or line-numbered views, pattern search, session-start reads, and path sanitization. Enforces read permissions.

## Terms

- Virtual name: the virtual file path used by the agent to identify files in the controlled workspace.
- Line-numbered view: a view of a file's content where each line is prefixed with its 1-indexed line number.
- Session-start read: a pre-injected plain read of a non-writable readable file presented before the agent's first turn.

## Contract

**Inputs**

- Per read or search: a virtual file path, regex pattern, offset, limit, or line-numbering flag.

**Operations**

- Read a file's content by virtual name.
- Search for a regex pattern across readable files.
- Provide session-start reads for non-writable files.
- Sanitize error messages and output by replacing real on-disk paths with virtual names.

**Guarantees**

- Reads of non-writable files provide plain content; reading an existing writable file requires the line-numbered view.
- Search provides matches only in read-only files; matches in writable files are reported as counts without content.
- Reads of read-only files and search results never set the supersession flag.
- Session-start reads are sorted by virtual name and skip missing or writable files.
- Sanitize paths replaces real on-disk paths with virtual names.
- No state persists across sessions.

**Assumptions**

- Files are UTF-8 encoded.

## Non-concerns

- File writing and modification: handled by file_editor.
- Template initialization: handled by file_editor.
