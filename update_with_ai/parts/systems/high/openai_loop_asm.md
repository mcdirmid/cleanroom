<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:57Z
LAST_CHANGED: 2026-10-11T02:45:00Z
CHANGE: Restate the root assembly structurally and remove the constituent enumeration from prose
CODE_HASH: d68f7d3bd0bb
SPEC_QA_AUDIT: 2026-10-15T19:43:57Z
-->

# openai_loop_asm assembly component

assembles: dag_asm, loop_asm, conversation_impl, driver_impl, logger_impl, sandbox_asm, uv_asm, loop_impl, model_config_impl
imports: session, commonmark_ext, filesystem_ext, json_ext, openai_ext, src_metadata_ext, manifest_ext, target_labels_ext
implements: agent_config, file_alias, node_config, node_storage, dag_config, dag_storage, subgraph, file_paths, loop, cleaner, conversation, driver, guard, node_cleaner, openai_config, logger, file_editor, file_reader, guide_delivery, run_control, template_format, tool_provider, manifest_loader, target

## Purpose

The openai_loop_asm assembly component aggregates the Cleanroom UV, DAG, loop, and sandbox assemblies along with the UV loop, OpenAI driver, conversation, configuration, and runner logger implementations into the complete Cleanroom UV OpenAI loop root system assembly.

Building an autonomous multi-agent development environment requires integrating methodology configuration parsing, persistent message delivery, topological DAG execution, language model interaction loops, and guarded sandbox toolkits into a single executable system. Fragmented assembly structures force entry points to orchestrate cross-cutting subsystem initializations imperatively, introducing initialization order defects and partial subsystem configurations. The openai_loop_asm assembly component forms the root assembly that closes all interface components across the application, resolving internal dependencies among sub-assemblies and leaving only external boundary protocols as external imports.

**Out of scope:** The openai_loop_asm assembly component does not parse command-line options, define remote provider communication protocols, or manage host operating system processes; these are handled by other components.

## Types and Behavior

The openai_loop_asm assembly component aggregates the implementations of every interface component in the application, uniting the constituent sub-assemblies and standalone implementations into a complete root system that is ready to execute.

The uv openai loop assembly initializes its constituent assemblies and implementations recursively, registering every singleton service across the system and session lifecycle tiers to achieve complete interface closure.
