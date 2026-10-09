<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-08T12:55:00Z
CHANGE: assemble workspace_tool_impl
CODE_HASH: 42f61aaf4101
-->

# cleanroom_asm assembly component

assembles: bazel_openai_loop_asm, control_asm, file_paths_impl, tools_asm, workspace_asm, workspace_tool_impl
imports: agent_session, bazel_manifest_ext, bazel_target_labels_ext, commonmark_ext, filesystem_ext, json_ext, model_config_ext, openai_ext, src_metadata_ext
implements: agent_config, agent_file_alias, agent_node_config, agent_storage, bazel_manifest_loader, bazel_target, control_attribution, control_coordinate, control_submit, control_verification, control_work_scheduler, dag_config, dag_storage, dag_subgraph, file_paths, loop, loop_cleaner, loop_conversation, loop_driver, loop_guard, loop_node_cleaner, openai_config, runner_logger, sandbox, sandbox_file_editor, sandbox_file_reader, sandbox_guide_delivery, sandbox_run_control, src_metadata, template_format, tool_coverage, tool_provider, workspace_provision, workspace_registry, workspace_sync, workspace_tool, workspace_work

## Purpose

The cleanroom_asm assembly component aggregates all Cleanroom subsystems into the unified master root system assembly that encompasses build automation, language model loops, session control, coverage evaluation, and isolated workspace management.

Operating an autonomous software development environment requires unifying build analysis, multi-agent coordination loops, in-band metadata management, statement coverage audits, and isolated workspace provisioning into a single cohesive dependency graph. Fragmented top-level targets prevent comprehensive build-graph traversal, impeding whole-subgraph status inspection and requiring multiple disjoint commands to certify system hygiene. The cleanroom_asm assembly component provides an exhaustive root assembly closing all internal subsystem interfaces and enabling unified lifecycle initialization and clean verification across the entire Cleanroom graph.

**Out of scope:** The cleanroom_asm assembly component does not implement custom tool logic, execute subprocesses directly, or define host process supervisors; these are handled by other components.

## Types and Behavior

The *cleanroom assembly* unites all constituent subsystem assemblies and implementations into a unified system ready for end-to-end execution. The cleanroom assembly initializes its constituent assemblies and implementations recursively, registering all singleton services across system and session lifecycle tiers to achieve full architectural interface closure.

The cleanroom assembly aggregates the following constituents:

- The bazel openai loop assembly from bazel_openai_loop_asm, closing the agent configuration, build target management, DAG graph traversal, language model driving loop, runner logging, and sandbox tool provider interfaces.

- The control assembly from control_asm, closing the session coordination, verification evaluation, work scheduling, submission handling, defect attribution, and in-band source metadata interfaces.

- The file paths implementation from file_paths_impl, closing the file paths interface to validate and normalize workspace paths.

- The tools assembly from tools_asm, closing the tool coverage interface to measure statement coverage and certify execution thresholds.

- The workspace assembly from workspace_asm, closing the workspace provisioning, workspace registry, workspace synchronization, and work queue interfaces.

- The workspace tool runner implementation from workspace_tool_impl, closing the workspace tool runner interface for role workspace CLI execution and argument parsing.
