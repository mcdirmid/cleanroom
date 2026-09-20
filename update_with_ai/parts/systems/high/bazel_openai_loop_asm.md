# bazel_openai_loop_asm assembly component

assembles: bazel_asm, bazel_loop_impl, bazel_openai_config_impl, dag_asm, loop_asm, runner_logger_impl, sandbox_asm
imports: bazel_target_labels_ext, commonmark_ext, filesystem_ext, json_manifest_ext, model_config_ext, openai_ext, update_with_ai_proto_ext
implements: agent_config, agent_file_alias, agent_node_config, agent_storage, bazel_manifest_loader, bazel_target, dag_config, dag_storage, dag_subgraph, file_paths, loop, loop_cleaner, loop_conversation, loop_driver, loop_guard, loop_node_cleaner, openai_config, runner_logger, sandbox, sandbox_file_editor, sandbox_file_reader, sandbox_guide_delivery, sandbox_run_control, template_format, tool_provider

## Purpose

The bazel_openai_loop_asm assembly component aggregates the Bazel, DAG, loop, and sandbox assemblies along with the Bazel loop, Bazel OpenAI configuration, and runner logger implementations into the complete Cleanroom Bazel OpenAI loop root system assembly.

Building an autonomous multi-agent development environment requires integrating build graph parsing, persistent message delivery, topological DAG execution, language model interaction loops, and guarded sandbox toolkits into a single executable system. Fragmented assembly structures force entry points to orchestrate cross-cutting subsystem initializations imperatively, introducing initialization order defects and partial subsystem configurations. The bazel_openai_loop_asm assembly component forms the root assembly that closes all interface components across the application, resolving internal dependencies among sub-assemblies and leaving only external boundary protocols as external imports.

**Out of scope:** The bazel_openai_loop_asm assembly component does not parse command-line options, define remote provider communication protocols, or manage host operating system processes; these are handled by other components.

## Types and Behavior

The *bazel openai loop assembly* unites the sub-assemblies and standalone implementations into a complete system that is ready to execute. The bazel openai loop assembly initializes its constituent assemblies and implementations recursively, registering all singleton services with the system lifecycle prototype to achieve complete interface closure.

The bazel openai loop assembly aggregates the following constituents:

- The bazel assembly from bazel_asm, closing the agent file alias, agent node config, agent storage, bazel manifest loader, bazel target, dag storage, and file paths interfaces.

- The bazel loop implementation from bazel_loop_impl, closing the loop interface to coordinate build graph execution and change propagation across workspace targets.

- The bazel openai config implementation from bazel_openai_config_impl, closing the agent config, dag config, and openai config interfaces to load language model parameters, execution limits, and authentication credentials.

- The dag assembly from dag_asm, closing the dag subgraph interface.

- The loop assembly from loop_asm, closing the loop cleaner, loop conversation, loop driver, loop guard, and loop node cleaner interfaces.

- The runner logger implementation from runner_logger_impl, closing the runner logger interface to stream terminal progress summaries and unbuffered transcript logs.

- The sandbox assembly from sandbox_asm, closing the sandbox, sandbox file editor, sandbox file reader, sandbox guide delivery, sandbox run control, template format, and tool provider interfaces.
