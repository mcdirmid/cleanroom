# mcp_server_impl implementation component

imports: dag_storage, dag_subgraph, fastmcp_ext, mcp_cache_arbiter, mcp_gate, mcp_server, mcp_session, tool_provider
implements: mcp_server

## Assumptions and Requirements

### Requirements

1. The next batch tool accepts a target unit address and a target role address, sets the target root node on the DAG subgraph using in-process system singletons without creating child registries, queries the DAG subgraph to determine the next ready batch of dirty nodes, and returns a JSON string with the unit, role, is_complete flag, ready_role, batch list, and dirty_nodes list.

## Grounding Facts

### Knowledge Needed

- Target unit address.
- Target role address.
- Ready batch state and completion status from `dag_subgraph.DagSubgraph`.

### Actions Needed

- Set target root node on `dag_subgraph.DagSubgraph`.
- Query next ready batch from `dag_subgraph.DagSubgraph`.
- Format wave resolution record into JSON response string.
