# run_control_impl

imports: tool_provider, virtual_file_name, dag_storage, dag_node_cleaner, change_summary_validator, run_control
types from tool_provider: tool metadata, tool result, tool failure, termination outcome
types from virtual_file_name: virtual file name
types from dag_storage: node
types from dag_node_cleaner: feedback message, change message
types from change_summary_validator: change summary, change validator
types from run_control: run control factory, run controller, advance tool, fail tool, blame tool, blame target
implements: run control factory

## Behavior

- Creating a *run controller* through a *run control factory* yields a *run controller* configured with verification commands, dependency blame targets, and a *change validator*.
- The *tool metadata* for the *advance tool* specifies the name `advance` and accepts an optional *change summary* parameter.
- The *tool metadata* for the *fail tool* specifies the name `fail` and accepts an explanation parameter.
- The *tool metadata* for the *blame tool* specifies the name `blame` and accepts target and explanation parameters.
- Executing the *advance tool* runs configured verification checks, requiring either validated file modifications or a passing verification check before terminating.
- When workspace file modifications occurred, the *advance tool* requires a *change summary* validated by a *change validator* within the configured length bound.
- Executing the *advance tool* produces a *change message* only when workspace files were modified.
- Executing the *blame tool* resolves the blamed *virtual file name* to its owning dependency *node* and forms a *feedback message*.
