# sandbox_run_control interface component

imports: tool_provider, agent_file_alias, dag_storage, agent_node_config

## Assumptions and Requirements

### Requirements

1. A resolve tool is a polymorphic tool service defining a file alias resolve target parameter identifying the active node being resolved.
2. The run controller exposes verification checks that validate session criteria.
3. The run controller caches verification evaluation results alongside edit manager file hashes for target nodes, reusing the cached verification outcome as long as no workspace files have been updated since that evaluation.
4. The run controller installs an argument-free check files tool named check_files that updates verification results if outdated, evaluates verification checks across all open targets and modified workspace files, presents aggregated verification outcomes to the agent, tracks last tested file hashes, and fails when verification failed.
5. The run controller installs an advance tool when guide step mode is active, coordinating step progression through guide delivery upon passing verification.
6. The run controller installs a submit tool which is a resolve tool that concludes active nodes upon passing verification, marks the resolve target clean in the current get work turn, accepting a text change summary parameter, and enforces change documentation.
7. The run controller installs a fail tool which is a resolve tool that terminates the run in failure, accepting a text explanation parameter.
8. The run controller installs a blame tool which is a resolve tool, attributing task failure to an upstream dependency node, accepting a file alias blame target parameter and a text explanation parameter.
9. The run controller installs a get work tool that retrieves active dirty nodes, materializes startup templates, accepting an integer max batch size parameter, delivers the session task prompt, and specifies a follow-up execution of the advance tool when the guide is in step mode.

## Grounding Facts

### Knowledge Needed

- Verification checks and cached evaluation results.
- Open targets and modified workspace files.
- Resolve target file aliases.
- Change summary and blame explanation parameters.
- Task prompt and incoming change messages.

### Actions Needed

- Install and execute `check_files` verification tool.
- Install and execute `advance` step progression tool.
- Install and execute `submit`, `fail`, and `blame` resolve tools.
- Install and execute `get_work` task dispatch tool.
