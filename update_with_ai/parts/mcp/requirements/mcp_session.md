# mcp_session interface component

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
- Active sessions registry.

### Actions Needed

- Initiate session phase scope.
- Configure role and unit root on configuration singletons.
- Record session as active.
- Close session scope and release resources.
