# mcp_session_impl implementation component

imports: agent_config, agent_node_config, agent_session, dag_storage, dag_subgraph, mcp_session
implements: mcp_session

## Assumptions and Requirements

### Requirements

1. Registering a session initiates an agent session phase scope, sets role on role config, configures unit root on dag subgraph, and records the session as active.
2. Deregistering a session closes the session scope, releasing held resources and file locks, and removes the session from the active registry.
3. Exposes all currently registered sessions mapped by conversation identifier.

## Grounding Facts

### Knowledge Needed

- Conversation identifier.
- Role address.
- Unit root.
- Active session registry.

### Actions Needed

- Initiate phase scope from `agent_session`.
- Set role on `agent_node_config`.
- Set unit root on `dag_subgraph.DagSubgraph`.
- Register session as active.
- Close phase scope and remove session from registry.
