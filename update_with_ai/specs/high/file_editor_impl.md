# file_editor_impl

imports: tool_provider, file_reader, virtual_file_name, file_editor
types from tool_provider: tool metadata, tool result, tool failure
types from file_reader: read-write file
types from virtual_file_name: virtual file name
types from file_editor: file editor factory, file editor, text replacement tool, line update tool, template
implements: file editor factory

## Behavior

- Creating a *file editor* through a *file editor factory* yields a *file editor* configured with writable permissions, host paths, and startup templates.
- The *tool metadata* for the *text replacement tool* specifies the name `replace` and accepts target text and replacement text parameters.
- Executing the *text replacement tool* with target text exceeding the maximum replacement size limit produces a *tool failure*.
- The *tool metadata* for the *line update tool* specifies the name `update_lines` and accepts 1-indexed start line, end line, and replacement text parameters.
- Executing the *line update tool* with a start line greater than the end line performs an insertion at the start line.
- Executing the *line update tool* with empty replacement text deletes the specified line range.
- Baseline file content is captured by a *file editor* before the first modification to a *read-write file*.
