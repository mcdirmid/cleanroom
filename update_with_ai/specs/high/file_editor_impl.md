# file_editor_impl

fulfills: file_editor
imports: file_reader (virtual name, line-numbered view), tool_provider (tool results, supersession flag, tool failures, tool call)
terms (from file_editor): file write, injected read, template
terms (from file_reader): virtual name, line-numbered view
terms (from tool_provider): supersession flag, tool failure, tool call, tool result

## Deltas

- Replaces at most 200 characters per string in `replace`; fails if strings exceed this limit.
- Supports 1-indexed line ranges in `update_lines`: `start_line > end_line` performs insertion, empty `new_str` deletes.
- Tracks `_file_views` per file (False for plain, True for line-numbered view); write resets view to plain until injected read sets it to line-numbered.
- Snapshots original file content before the first write of each file for diff verification.

## Non-concerns

- Line ending normalization: standard LF line endings are used.
