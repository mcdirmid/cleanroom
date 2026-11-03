# autofab_asm assembly component

assembles: control_asm, file_paths_impl, metadata_asm, workspace_cli_asm, dag_asm, uv_asm, workspace_asm
imports: session, commonmark_ext, filesystem_ext, json_ext, model_config_ext, src_metadata_ext, manifest_ext, target_labels_ext
implements: agent_config, file_alias, node_config, node_storage, attribution, coordinate, submit, verification, work_scheduler, dag_config, dag_storage, subgraph, file_paths, src_metadata, coverage, manifest_loader, target, provision, role_registry, roles, scaffold, sync, cli_tool, work

## Purpose

The autofab_asm assembly component aggregates all Autofab UV subsystems into the unified master root system assembly that encompasses methodology configuration, language model loops, session control, coverage evaluation, and isolated workspace management.

Operating an autonomous software development environment requires unifying specification analysis, multi-agent coordination loops, in-band metadata management, statement coverage audits, and isolated workspace provisioning into a single cohesive dependency graph. Fragmented top-level targets prevent comprehensive build-graph traversal, impeding whole-subgraph status inspection and requiring multiple disjoint commands to certify system hygiene. The autofab_asm assembly component provides an exhaustive root assembly closing all internal subsystem interfaces and enabling unified lifecycle initialization and clean verification across the entire Autofab graph.

**Out of scope:** The autofab_asm assembly component does not implement custom tool logic, execute subprocesses directly, or define host process supervisors; these are handled by other components.

## Types and Behavior

The autofab_asm assembly component aggregates the implementations of every interface component in the system, uniting the constituent subsystem assemblies and implementations into a unified root system that is ready for end-to-end execution.

The uv autofab assembly initializes its constituent assemblies and implementations recursively, registering every singleton service across the system and session lifecycle tiers to achieve full architectural interface closure.

<!-- AUTOFAB METADATA
LAST_CLEANED: 2026-10-15T19:43:57Z
LAST_CHANGED: 2026-10-29T17:15:00Z
CHANGE: Rename cleanroom_asm to autofab_asm
SPEC_QA_AUDIT: 2026-10-15T19:43:57Z
-->
