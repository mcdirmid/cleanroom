# agent_file_alias interface component

imports: agent_session, dag_storage, file_paths, tool_provider

## Assumptions and Requirements

### Requirements

1. A file alias displays itself by its relative path when converted to a string.
2. The alias manager is an agent session service configured with the absolute path of a workspace root.
3. The alias manager is a parameter type with python type file alias and wire type string so file aliases can be tool parameters.
4. Converting a wire type string produces a matching read-only or read-write file if its relative path matches a declared bound file.
5. Converting a wire type string produces an unbound file if the relative path does not match a declared bound file.
6. Sanitizing text masks occurrences of relative workspace paths and preceding path prefixes with file alias relative paths so that agents observe file aliases rather than environment paths.

## Grounding Facts

### Knowledge Needed

- Workspace root absolute path.
- Bound files mapping.
- Relative workspace path patterns.

### Actions Needed

- Convert wire string into file alias entity.
- Match relative path against bound files.
- Mask workspace path occurrences in text with file aliases.
