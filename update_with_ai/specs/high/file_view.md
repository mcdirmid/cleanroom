# file_view

imports: tool_provider (tool results)
terms (from tool_provider): tool failure
terms (owned): virtual name, file write, line-numbered view, injected read, session-start read, template

## Purpose

Provides the file machinery of a controlled workspace: virtual-name addressing, reading, writing, content-based editing, line-range editing, recursive searching, session-start reads, and template initialization. Enforces per-file permissions and tracks whether any file write has occurred.

## Terms

- Virtual name: the name the agent uses to refer to a file; it is the file's final path component when no other file in the workspace shares that component, and otherwise the file's path with just enough leading components removed to be unique among the workspace's files; the component resolves the virtual name to the file's full filesystem path.
- File write: any successful operation that modifies the filesystem.
- Line-numbered view: a rendering of a file's content with each line prefixed by its 1-indexed line number; the line numbers are metadata, never file content.
- Injected read: the read provided for a file immediately after a successful file write of that file, presenting a read request with line numbers and the read result carrying the file's full current content; the agent did not request it, and to the agent it appears as a numbered read it requested.
- Session-start read: a read of a file the agent can read but not write, provided at run start for rendering before the agent's first turn; it renders the file's content plain, never supersedes an earlier result, and is never stubbed.
- Template: a writable file's initial content, configured for the file; when the file does not exist when the component is configured, the file is created with the template's content at run start; a file that exists when the component is configured is never modified by its template.

## Contract

**Inputs**

- Configured: file mappings (virtual name to full path); the readable and writable virtual names; the templates (a mapping from writable virtual names to their template content; may be empty); the search result limit (the maximum matches a single search may render); whether session-start reads are enabled.
- Per call: a tool call (tool name and arguments, per tool_provider).

**Operations**

- Request tool definitions (per tool_provider).
- Execute a tool call.
- Query whether any file write has occurred.
- Request the session-start reads.

**Guarantees**

- Permissions are enforced for all operations.
- Signals whether any file write has occurred.
- Files are addressed to the agent by their virtual names, never by their paths.
- Path sanitization maps any host filesystem paths, sandbox paths, or package prefixes to their corresponding virtual names.
- Files with the same final path component have distinct virtual names: each retains just enough of its path to differ from every other file's virtual name.
- Reads, writes, edits, searches, session-start reads, and error messages name files by their virtual names.
- A read provides the file's entire content; reads are not paginated and are not bounded by a size limit.
- Content-based editing: search-and-replace of short text, bounded in length; longer changes go through line-range editing.
- Line-range editing: replace, delete, insert.
- Recursive searching within a specified path (or across all readable files when the path specifies a root, directory prefix, is empty, or is omitted).
- Search results beyond the search result limit signal a tool failure advising offset/limit pagination; the limit bounds rendered matches only.
- Search results render matches only for files that are not writable; matches in writable files are reported as counts without content.
- An edit's replacement applies atomically (all or nothing).
- Reads of writable files provide line numbers, enabling line-range edits; a plain read of an existing writable file is rejected; reads of non-writable files provide plain content.
- Line-range edits require a numbered read; attempting one without it signals a tool failure.
- Line-range edits accept 1-indexed line numbers within the file's current bounds (allowing insertion into empty files).
- Stubbing replaces superseded tool results with placeholders, keeping the conversation focused on current state.
- After a successful file write, the file's current content appears in the conversation.
- A write that fails does not provide the file's content.
- When session-start reads are enabled, a session-start read is provided for every file that is readable but not writable; when disabled, none are provided.
- Session-start reads are provided in a deterministic order (sorted by virtual name).
- A session-start read renders the file's content plain and never supersedes an earlier result.
- Files with templates are initialized from their template content at run start.
- Template initialization is not a file write: it never signals that the filesystem was modified and is never a changed file.
- Tool definitions state each tool's purpose, parameters, bounds, and preconditions, contrasting content-based editing with line-range editing.
- Error messages identify the violated policy or the failing operation; errors leave the filesystem unchanged.

**Assumptions**

- The consumer stubs the earlier result when a result's flag is set, identifying it by the file's virtual name.
- A file the agent reads or edits exists on disk as a regular file, or is created by a file write or by template initialization.

## Non-concerns

- Error message wording: error messages identify the violated policy or the failing operation; their exact wording is unspecified.
- Session-start read size: session-start reads inherit the unbounded-read rule; the read-only files are assumed to be reasonably sized, so no separate size bound is introduced for session-start reads.
- Template size: templates are assumed to be reasonably sized, so no separate size bound is introduced for template content.
- Virtual-name derivation: the exact procedure that selects the shortest unique suffix is unspecified; the resulting virtual names follow the virtual name definition.
