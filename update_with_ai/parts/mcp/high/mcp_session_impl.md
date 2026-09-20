# mcp_session_impl implementation component

imports: agent_config, agent_node_config, agent_session, dag_storage, dag_subgraph
implements: mcp_session

## Purpose

The mcp_session_impl implementation component realizes role sub-agent session registration, scope lifecycle activation, and timestamp tracking using the lifecycle framework.

Coordinating long-lived multi-turn sessions across external JSON-RPC boundaries requires precise synchronization between asynchronous call arrivals and scoped service instantiation. Without an explicit session lifecycle adapter, concurrent tool calls risk accessing inactive scopes or triggering uncoordinated teardown of active singletons. The mcp_session_impl implementation component bridges external conversation identifiers to discrete lifecycle phase scopes, configuring role parameters, initializing mcp mode, and executing LIFO teardown upon deregistration.

**Out of scope:** The mcp_session_impl implementation component does not parse build files, dispatch sampling messages, or evaluate verification checks; these are handled by other components.

## Types and Behavior

The role session manager maintains registered role agent sessions in an internal mapping keyed by conversation identifier.

Registering a session validates that no active session is currently registered for the specified conversation identifier, signaling an error if a session already exists.

When registering a session:

- An agent session phase scope is initiated using the lifecycle begin phase operation, establishing an open scope that persists across discrete turns without binding to a context manager.

- Within the initiated scope, mcp mode is activated on the agent config, the role of the session is configured on the role config, and the target unit root is configured on the dag subgraph with a root node constructed for the unit address and role address in dag storage.

- The created role agent session is recorded in the active sessions mapping with the current system timestamp and an active status.

Deregistering a session resolves the role agent session for the conversation identifier, signaling an error if no session is registered. The session scope is closed using the scope close operation, executing singleton teardowns in reverse instantiation order and releasing all acquired locks. The session record is removed from the active sessions mapping.

Resolving a session scope retrieves the lifecycle scope when registered, or produces an empty outcome when absent. Touching a session updates the last active timestamp with the current time and ensures the session status is active. Transitioning session status updates the recorded status for the registered session.
