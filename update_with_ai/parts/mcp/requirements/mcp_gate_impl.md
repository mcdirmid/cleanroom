# mcp_gate_impl implementation component

imports: filesystem_ext, mcp_gate, mcp_session, sandbox_file_editor, sandbox_file_reader
implements: mcp_gate

## Assumptions and Requirements

### Requirements

1. Validating access resolves tool permissions for the conversation and target file path, producing an access decision.
2. Filtering directory listings sanitizes child entries for the conversation and target directory path, preserving role blindness.

## Grounding Facts

### Knowledge Needed

- Tool permissions for active session from `mcp_session.RoleSessionManager`.
- Target file path.
- Target directory path.
- Registered role blindness exclusions.

### Actions Needed

- Resolve active session from `mcp_session.RoleSessionManager`.
- Validate file read or edit access permissions.
- Filter directory entries using `filesystem_ext` to remove out-of-scope paths.
