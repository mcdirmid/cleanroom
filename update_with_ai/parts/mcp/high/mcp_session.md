# mcp_session interface component

imports: agent_config, agent_session, dag_subgraph

## Purpose

The mcp_session interface component defines multi-turn session lifecycle management, active session registry, and turn scope activation for role sub-agents.

Desktop agent environments invoke tools across discrete asynchronous turns where process state must persist across invocations while maintaining isolated session boundaries. Without centralized session lifecycle governance, concurrent sub-agents risk colliding file locks, leaking session resources, and encountering premature teardown. The mcp_session interface component establishes an ambient system registry that manages sub-agent session lifecycles, maps conversation identifiers to active scopes, and activates scoped phases during tool turns.

**Out of scope:** The mcp_session interface component does not serialize network wire protocols, validate file edits, or format task prompts; these are handled by other components.

## Types and Behavior

A *conversation identifier* is data identifying a sub-agent conversation, wrapping a string value.

A *session status* is the operational state of a role sub-agent session, distinguishing between an *active* session currently executing or ready for turns, an *idle* session waiting for upstream tasks, and a *terminated* session that has concluded.

A *role agent session* is data recording the runtime state of a sub-agent session.

A role agent session provides:

- The conversation identifier uniquely addressing the sub-agent conversation.

- The *role address* specifying the engineering role label of the session.

- The *unit root* specifying the target unit sub-graph root label.

- The *lifecycle scope* governing session-scoped services.

- The *last active timestamp* recording the time of the most recent interaction turn.

- The session status.

The *role session manager* is a system service that maintains active role agent sessions.

The role session manager:

- Can *register session* with a conversation identifier, a role address, and a unit root, creating and opening an agent session phase scope, initializing session configuration, and recording the session as active.

- Can *deregister session* with a conversation identifier, closing the session scope, releasing held resources and file locks, and removing the session from the active registry.

- Can *get session scope* with a conversation identifier to retrieve the open lifecycle scope for that conversation.

- Can *touch session* with a conversation identifier, updating its last active timestamp to the current time.

- Can *set session status* with a conversation identifier and a session status, transitioning the session between active and idle states.

- Can *get session* with a conversation identifier to retrieve the role agent session record.

- Exposes *active sessions* as all currently registered sessions mapped by conversation identifier.
