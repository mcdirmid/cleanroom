# sandbox_impl implementation component

imports: tool_provider, sandbox_file_reader, sandbox_file_editor, sandbox_run_control, node_config, model_config
implements: sandbox

## Purpose

The sandbox_impl implementation component realizes startup tool execution assembly, template materialization, and modification tracking for agent sessions.

Agent sessions require initial context assembled from multiple services before execution begins. The sandbox_impl implementation component integrates peer session services—the read manager, edit manager, and run controller—assembling baseline tool executions, delegating template materialization, and exposing session-wide file modification state.

**Out of scope:** The sandbox_impl implementation component does not parse tool arguments, format diff patches, or manage run outcome termination; these are handled by other components.

## Types and Behavior

Retrieving startup tool executions assembles an ordered sequence of initial tool executions based on active configuration in the model config from model_config and file definitions in the node config from node_config. When using step mode in the model config to communicate a guide progressively, the sandbox includes an initial startup tool execution setting the tool name to `advance`, providing empty wire parameter bindings, and executing the advance tool from the run controller to capture the response. When performing startup reads in the model config to inspect declared files at session start, the sandbox queries the read manager for declared read-only files from node config and appends a startup tool execution for each file, setting the tool name to `read_file`, constructing wire parameter bindings mapping `file` to the file's short name and omitting line numbers, and executing the read tool to capture the response.

Materializing startup templates delegates to the edit manager to populate missing read-write files with starter templates from node config without overwriting existing files. The sandbox queries the edit manager to determine whether workspace file modifications occurred during the session.
