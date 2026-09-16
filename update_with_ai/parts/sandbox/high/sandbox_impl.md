# sandbox_impl implementation component

imports: agent_config, agent_node_config, sandbox_file_editor, sandbox_file_reader, sandbox_run_control, tool_provider
implements: sandbox

## Purpose

The sandbox_impl implementation component realizes startup tool execution assembly, template materialization, and modification tracking for agent sessions.

Agent sessions require initial context assembled from multiple services before execution begins. The sandbox_impl implementation component integrates peer session services—the read manager, edit manager, and run controller—assembling baseline tool executions, delegating template materialization, and exposing session-wide file modification state.

**Out of scope:** The sandbox_impl implementation component does not parse tool arguments, format diff patches, or manage run outcome termination; these are handled by other components.

## Types and Behavior

The sandbox configures startup context and tracks file modifications.

Startup tool executions are determined by session configuration:

- An initial advance tool execution with the name of the advance tool, empty wire parameter bindings, and the response produced by executing the advance tool is included when using step mode to communicate a guide progressively.

- File read executions for all declared read-only files ordered deterministically by file alias short name are included when performing startup reads and the session has at most one read-write file, positioned after any advance tool execution. Each file read execution uses the name of the view file tool, specifies wire parameter bindings mapping the path parameter of the view file tool to the read-only file alias short name, and captures the response produced by executing the view file tool.

- Omitted tool executions correspond to unconfigured options: when step mode is not used, startup tool executions contain no advance tool execution; when startup reads are not performed or the session has multiple read-write files, startup tool executions contain no file read executions.

Startup templates materialize missing read-write files with starter templates without overwriting existing files. Workspace file modifications report whether any read-write file was modified during the session.
