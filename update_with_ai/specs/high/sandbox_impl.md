# sandbox_impl implementation component

imports: tool_provider, sandbox_file_reader, sandbox_file_editor, sandbox_run_control, node_config, model_config
implements: sandbox

## Purpose

The sandbox_impl implementation component realizes startup tool execution assembly, template materialization, and modification tracking for agent sessions.

Agent sessions require initial context assembled from multiple services before execution begins. The sandbox_impl implementation component integrates peer session services—the read manager, edit manager, and run controller—assembling baseline tool executions, delegating template materialization, and exposing session-wide file modification state.

**Out of scope:** The sandbox_impl implementation component does not parse tool arguments, format diff patches, or manage run outcome termination; these are handled by other components.

## Types and Behavior

The session environment configures startup context and tracks file modifications.

For startup tool executions:

- When using step mode to communicate a guide progressively, startup tool executions include an initial advance tool execution with the name of the advance tool, empty wire parameter bindings, and the response produced by executing the advance tool.

- When performing startup reads to inspect declared files at session start, startup tool executions include file read executions for all declared read-only files from node config ordered deterministically by file alias short name, positioned after any advance tool execution. Each file read execution uses the name of the read tool, specifies wire parameter bindings mapping the file alias parameter of the read tool to the read-only file alias short name while omitting line numbers, and captures the response produced by executing the read tool.

- When step mode is not used, startup tool executions contain no advance tool execution; when startup reads are not performed, startup tool executions contain no file read executions.

Startup templates materialize missing read-write files with starter templates from node config without overwriting existing files. Workspace file modifications report whether any read-write file was modified during the session.
