# file_editor

imports: tool_provider, file_reader, virtual_file_name
types from tool_provider: tool, tool provider, tool result, tool failure
types from file_reader: read-write file
types from virtual_file_name: virtual file name

## Purpose

Enables surgical, reversible workspace file modifications while preventing context bloat and destructive rewrites.

Full-file rewrites waste output tokens and introduce accidental omissions, so modifications are restricted to targeted text replacements and line-range updates. Starter templates populate missing files without overwriting existing progress.

## Types

- A *text replacement tool* is a *tool* that replaces matching text within a *read-write file* identified by a *virtual file name*
- A *line update tool* is a *tool* that replaces a range of lines within a *read-write file* identified by a *virtual file name*
- A *file editor* is a *tool provider* providing a *text replacement tool* and a *line update tool*
- A *file editor factory* is a provider that constructs *file editors* configured for specific sessions
- A *template* is initial content for a *read-write file*

## Behavior

- Creating a *file editor* through a *file editor factory* yields a *file editor* configured with *read-write files*, path mappings, and *templates*.
- A *file editor* provides a *text replacement tool* and a *line update tool*.
- Executing a *file editor* tool with an unmapped or non-writable *virtual file name* produces a *tool failure*.
- Executing a *text replacement tool* with unique matching text replaces that text in the target *read-write file*.
- Executing a *text replacement tool* when matching text is ambiguous or absent produces a *tool failure*.
- Executing a *line update tool* with valid line bounds replaces the specified line range in the target *read-write file*.
- Executing a *line update tool* with invalid line bounds produces a *tool failure*.
- A *file editor* materializes *templates* into missing *read-write files* without overwriting existing files.
