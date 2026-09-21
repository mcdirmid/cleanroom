# mcp_gate_impl implementation component

imports: filesystem_ext, mcp_session, sandbox_file_editor, sandbox_file_reader
implements: mcp_gate

## Purpose

The mcp_gate_impl implementation component realizes hook access verification, workspace path normalization, and role blindness directory filtering using session guard tools.

Desktop lifecycle hooks execute as lightweight external processes that report raw host paths and tool names on standard input. Translating these external events into sound domain access decisions requires robust workspace path canonicalization, correlation to active sub-agent sessions, and delegation to session-scoped guard tools. The mcp_gate_impl implementation component normalizes paths against the workspace root, activates the session scope for the conversation, and queries read and edit managers to enforce file permissions and lock immutability.

**Out of scope:** The mcp_gate_impl implementation component does not spawn HTTP servers, manage git revisions, or construct test graphs; these are handled by other components.

## Types and Behavior

The access gate resolves the active session scope for the specified conversation identifier using the role session manager. If no session is registered for the conversation identifier, validating access produces a denied access decision explaining that no active session exists.

Host absolute paths are normalized into repository-relative workspace paths by resolving against the workspace root. Rejection occurs when paths fall outside the workspace root, producing a denied access decision.

Validating access resolves tool permissions inside the activated session scope:

- For file write tools matching `replace_file_content` or `write_to_file`, the access gate executes can write on the edit manager with the normalized path, producing an allowed access decision when the operation succeeds, or a denied access decision carrying the diagnostic content when denied.

- For file read tools matching `view_file`, the access gate executes can read on the read manager with the normalized path, producing an allowed access decision when the operation succeeds, or a denied access decision carrying the diagnostic content when denied.

- For unhandled tool names, the access gate produces a denied access decision indicating that the tool is not permitted under access gating.

Filtering directory listings sanitizes entries inside the activated session scope using can read on the read manager. The access gate tests candidate child file entries against can read, retaining entries that are readable and omitting entries that violate role blindness or target boundaries. If no session scope is registered for the conversation identifier, directory filtering returns an empty sequence of entries to fail closed.
