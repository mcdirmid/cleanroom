# loop interface component

imports: dag_storage

## Assumptions and Requirements

### Requirements

1. The loop executes a cleaning pass over an acyclic subgraph rooted at a target node in graph storage.
2. The loop produces a build result upon pass completion.
3. The loop marks a target node dirty by injecting a change message into its pending messages.
4. The loop injects a caller-supplied feedback message into a target node.
5. The loop broadcasts a caller-supplied change message from a node to all of its reverse dependencies.

## Grounding Facts

### Knowledge Needed

- Target root node.
- Graph storage nodes and pending messages.
- Build result outcome.
- Reverse dependencies of nodes.

### Actions Needed

- Execute cleaning pass over subgraph.
- Inject change or feedback messages into target nodes.
- Broadcast change messages to reverse dependencies.
