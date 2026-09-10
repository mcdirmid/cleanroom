# bazel_asm assembly component

imports: bazel_target_labels_ext, filesystem_ext, json_manifest_ext, model_config_ext, openai_ext, update_with_ai_proto_ext
implements: agent_conversation_history, agent_loop_guard, agent_node_cleaner, agent_runner, bazel_graph_storage, bazel_manifest_loader, bazel_node_id_utils, bazel_runner, dag_cleaner, dag_node_cleaner, dag_storage, file_alias, file_paths, model_config, node_config, runner_logger, sandbox, sandbox_change_summary_validator, sandbox_file_editor, sandbox_file_reader, sandbox_guide_delivery, sandbox_run_control, tool_provider

## Purpose

The bazel_asm assembly component aggregates Bazel build coordination, workspace manifest loading, dependency graph storage, message persistence, and execution configuration along with agent, DAG, and sandbox subsystems into the complete Cleanroom Bazel system assembly.

Building an autonomous multi-agent development environment requires integrating build graph parsing, persistent message delivery, topological DAG execution, language model interaction loops, and guarded sandbox toolkits into a single executable system. Fragmented assembly structures force entry points to orchestrate cross-cutting subsystem initializations imperatively, introducing initialization order defects and partial subsystem configurations. The bazel_asm assembly component forms the root assembly that closes all interface components across the application, resolving internal dependencies among sub-assemblies and leaving only external boundary protocols as external imports.

**Out of scope:** The bazel_asm assembly component does not parse command-line options, define remote provider communication protocols, or manage host operating system processes; these are handled by other components.

## Types and Behavior

The *bazel assembly* unites the sub-assemblies and Bazel workspace implementations into a complete system that is ready to execute. The bazel assembly initializes its constituent assemblies and implementations recursively, registering all singleton services with the system lifecycle prototype to achieve complete interface closure.

The bazel assembly aggregates the following constituents:

- The file paths implementation from file_paths_impl, closing the file paths interface to create, validate, and resolve path representations against the physical workspace root.

- The bazel runner implementation from bazel_runner_impl, closing the bazel runner interface to coordinate build graph execution and change propagation across workspace targets.

- The bazel manifest loader implementation from bazel_manifest_loader_impl, closing the bazel manifest loader interface to parse JSON manifests, resolve node references, and compute dependency closures.

- The bazel graph storage implementation from bazel_graph_storage_impl, closing the bazel graph storage and dag storage interfaces to provide in-memory graph indexing and durable message and reverse dependency persistence.

- The bazel node identifier utility implementation from bazel_node_id_utils_impl, closing the bazel node identifier utility interface to normalize target labels and resolve package directory paths.

- The bazel model config implementation from bazel_model_config_impl, closing the model config interface to load language model parameters and authentication credentials.

- The bazel node config implementation from bazel_node_config_impl, closing the node config and file alias interfaces to configure target session boundaries and resolve sanitized file aliases.

- The runner logger implementation from runner_logger_impl, closing the runner logger interface to stream terminal progress summaries and unbuffered transcript logs.

- The agent assembly from agent_asm, closing the agent runner, agent conversation history, agent loop guard, agent node cleaner, and dag node cleaner interfaces.

- The dag assembly from dag_asm, closing the dag cleaner interface.

- The sandbox assembly from sandbox_asm, closing the sandbox, sandbox file reader, sandbox file editor, sandbox run control, sandbox guide delivery, sandbox change summary validator, and tool provider interfaces.
