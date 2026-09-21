# bazel_mcp_system_asm assembly component

assembles: bazel_asm, cleanroom_mcp_runner_impl, dag_asm, mcp_asm, runner_logger_impl, sandbox_asm
imports: bazel_target_labels_ext, commonmark_ext, fastmcp_ext, filesystem_ext, json_manifest_ext, update_with_ai_proto_ext
implements: agent_config, agent_file_alias, agent_node_config, agent_storage, bazel_manifest_loader, bazel_target, cleanroom_mcp_runner, dag_config, dag_storage, dag_subgraph, file_paths, mcp_cache_arbiter, mcp_gate, mcp_server, mcp_session, runner_logger, sandbox, sandbox_file_editor, sandbox_file_reader, sandbox_guide_delivery, sandbox_run_control, template_format, tool_provider

## Purpose

The bazel_mcp_system_asm assembly component aggregates the Bazel, DAG, MCP, and sandbox assemblies along with the runner logger and cleanroom mcp runner implementations into the complete Cleanroom Bazel Model Context Protocol root system assembly.

Operating an autonomous sub-agent orchestration harness within external desktop environments requires integrating build manifest resolution, topological DAG evaluation, guarded sandbox toolkits, and FastMCP protocol servers into a unified executable system. Fragmented assembly structures force server entry points to orchestrate cross-cutting subsystem initializations imperatively, introducing initialization order defects and partial subsystem configurations. The bazel_mcp_system_asm assembly component forms the root assembly that closes all interface components across the application, resolving internal dependencies among sub-assemblies and leaving only external boundary protocols as external imports.

**Out of scope:** The bazel_mcp_system_asm assembly component does not parse command-line options, define remote provider communication protocols, or manage host operating system processes; these are handled by other components.

## Types and Behavior

The *bazel mcp system assembly* unites the sub-assemblies and standalone implementations into a complete system that is ready to execute. The bazel mcp system assembly initializes its constituent assemblies and implementations recursively, registering all singleton services with the system lifecycle prototype to achieve complete interface closure.

The bazel mcp system assembly aggregates the following constituents:

- The bazel assembly from bazel_asm, closing the agent file alias, agent node config, agent storage, bazel manifest loader, bazel target, dag storage, and file paths interfaces.

- The cleanroom mcp runner implementation from cleanroom_mcp_runner_impl, closing the cleanroom mcp runner interface to parse arguments and execute the server.

- The dag assembly from dag_asm, closing the dag subgraph interface.

- The mcp assembly from mcp_asm, closing the agent config, dag config, mcp cache arbiter, mcp gate, mcp server, and mcp session interfaces.

- The runner logger implementation from runner_logger_impl, closing the runner logger interface to stream terminal progress summaries and unbuffered transcript logs.

- The sandbox assembly from sandbox_asm, closing the sandbox, sandbox file editor, sandbox file reader, sandbox guide delivery, sandbox run control, template format, and tool provider interfaces.
