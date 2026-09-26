# antigravity_mcp_client interface component

## Assumptions and Requirements

### Requirements

1. The antigravity mcp client dispatches a tool name with an arguments mapping to a server port.
2. The antigravity mcp client establishes a session identifier with an assigned role and unit root.
3. The antigravity mcp client terminates a session identifier on the server.
4. The antigravity mcp client retrieves task instructions and incoming changes for a session identifier.
5. The antigravity mcp client runs batch verification tests for a session identifier.
6. The antigravity mcp client commits changes for an open target with a change summary.
7. The antigravity mcp client reports contract defects to a blame target with an explanation.
8. The antigravity mcp client stops the server on the server port.
9. The antigravity mcp client queries the next ready wave for a target unit.

## Grounding Facts

### Knowledge Needed

- Server network location.
- Session parameters.
- Target modification details.
- Blame defect details.

### Actions Needed

- Dispatch tool call with arguments to server.
- Register and terminate session on server.
- Query work items and batch verification.
- Submit target modifications or report blame defect.
- Shut down server.
- Query next wave batch.
