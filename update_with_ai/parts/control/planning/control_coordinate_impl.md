# control_coordinate_impl implementation component

imports: agent_session, dag_storage, control_verification, control_work_scheduler, control_submit, control_attribution, agent_node_config, agent_file_alias, dag_subgraph
implements: control_coordinate

## Intent

The control_coordinate_impl implementation component provides concrete mechanics for session node registration, default target resolution algorithms, and dispatching to constituent control services.

The implementation maintains session dictionaries mapping `DagNode` instances to states (`OPEN`, `CLEAN`, `FAILED`, `ATTRIBUTED`) and file aliases, resolves string arguments to target nodes, routes commands to specialized coordinators, and aggregates outcomes into control dispatch outcomes.

## Factored Contracts

### Contracts

- The session coordinator maintains an in-memory dictionary of node target states. [store_node_states]
- The session coordinator maps file alias strings to registered dag nodes. [map_alias_to_node]
- The session coordinator selects the single open node when only one open target remains. [default_single_open_node]
- The session coordinator selects the open node corresponding to the last modified file. [default_last_modified_file]
- The session coordinator invokes the work scheduler to discover tasks and populates session nodes. [populate_scheduled_nodes]
- The session coordinator delegates verification to the verification evaluator. [delegate_verification]
- The session coordinator delegates submission to the submission coordinator. [delegate_submission]
- The session coordinator delegates attribution to the attribution coordinator. [delegate_attribution]

## Woven Contracts

- When resolving a default target with multiple open nodes, the coordinator checks last modified file timestamps to pick the active node. [default_last_modified_file, control_coordinate: [resolve_default_target_contract]]
- When get work is called, the coordinator invokes the work scheduler, stores newly discovered nodes as open, and returns the work schedule. [populate_scheduled_nodes, store_node_states, control_coordinate: [dispatch_get_work]]
- When check files is called, the coordinator evaluates single or multiple targets via the verification evaluator and returns the combined results. [delegate_verification, control_coordinate: [dispatch_check_files]]
