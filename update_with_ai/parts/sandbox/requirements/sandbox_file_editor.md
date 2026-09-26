# sandbox_file_editor interface component

imports: agent_session, agent_file_alias, tool_provider

## Assumptions and Requirements

### Requirements

1. A file template is file content representing initial boilerplate for a read-write file.
2. The replace file content tool is an editing tool that replaces target content with replacement content in a read-write file within a line range bounded by a start line and end line, or across multiple occurrences when multiple replacements are permitted.
3. Materializing templates populates missing read-write files with initial template content without overwriting existing files.
4. The edit manager exposes whether workspace file writes occurred during the session, determined by whether workspace file contents differ from their initial state prior to editing.
5. The edit manager computes a file hash for a read-write file from its content.
6. The edit manager exposes a file update revision that tracks sequential updates made to workspace files.
7. The edit manager tracks the last read or edited file across the session, updating the last read or edited file when recording a file read.
8. Recording a file edit updates the last read or edited file and increments the file update revision.
9. The edit manager provides a can write operation validating write access for a read-write file.

## Grounding Facts

### Knowledge Needed

- Read-write file paths and initial content state.
- Line range bounds and replacement content.
- File hash values and file update revision counter.
- Last read or edited file tracking.

### Actions Needed

- Replace target content within line range or across file.
- Materialize initial templates for missing files.
- Track file update revision and content modifications.
- Validate write access for target file.
