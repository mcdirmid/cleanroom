# cleanroom_asm assembly component

assembles: control_asm, file_paths_impl, metadata_asm, workspace_cli_asm, openai_loop_asm, workspace_asm
imports: session, commonmark_ext, filesystem_ext, json_ext, model_config_ext, openai_ext, src_metadata_ext, manifest_ext, target_labels_ext
implements: agent_config, file_alias, node_config, node_storage, attribution, coordinate, submit, verification, work_scheduler, dag_config, dag_storage, subgraph, file_paths, loop, cleaner, conversation, driver, guard, node_cleaner, openai_config, logger, file_editor, file_reader, guide_delivery, run_control, src_metadata, template_format, coverage, tool_provider, manifest_loader, target, provision, role_registry, roles, scaffold, sync, cli_tool, work

## Purpose

The cleanroom_asm assembly component aggregates all Cleanroom UV subsystems into the unified master root system assembly that encompasses methodology configuration, language model loops, session control, coverage evaluation, and isolated workspace management.

Operating an autonomous software development environment requires unifying specification analysis, multi-agent coordination loops, in-band metadata management, statement coverage audits, and isolated workspace provisioning into a single cohesive dependency graph. Fragmented top-level targets prevent comprehensive build-graph traversal, impeding whole-subgraph status inspection and requiring multiple disjoint commands to certify system hygiene. The cleanroom_asm assembly component provides an exhaustive root assembly closing all internal subsystem interfaces and enabling unified lifecycle initialization and clean verification across the entire Cleanroom graph.

**Out of scope:** The cleanroom_asm assembly component does not implement custom tool logic, execute subprocesses directly, or define host process supervisors; these are handled by other components.

## Types and Behavior

The cleanroom_asm assembly component aggregates the implementations of every interface component in the system, uniting the constituent subsystem assemblies and implementations into a unified root system that is ready for end-to-end execution.

The uv cleanroom assembly initializes its constituent assemblies and implementations recursively, registering every singleton service across the system and session lifecycle tiers to achieve full architectural interface closure.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:57Z
LAST_CHANGED: 2026-10-11T02:45:00Z
CHANGE: Restate the root assembly structurally and remove the constituent enumeration from prose
SPEC_QA_AUDIT: 2026-10-15T19:43:57Z
-->
