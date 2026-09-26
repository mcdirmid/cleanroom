# mcp_gate interface component

imports: mcp_session

## Assumptions and Requirements

### Requirements

1. Validating access resolves tool permissions for the conversation and target file path, producing an access decision.
2. Filtering directory listings sanitizes child entries for the conversation and target directory path, preserving role blindness.

## Grounding Facts

### Knowledge Needed

- Tool permissions for the conversation.
- Target file path.
- Target directory path.
- Role blindness filtering rules.

### Actions Needed

- Validate tool access permissions for file operations.
- Sanitize directory child entries to preserve role blindness.
