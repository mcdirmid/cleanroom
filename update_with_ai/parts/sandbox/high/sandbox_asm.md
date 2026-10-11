<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Reduce the assembly narrative to a single structural sentence and remove collaborator naming from prose
CODE_HASH: 4c375e5af26f
SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
-->

# sandbox_asm assembly component

assembles: sandbox_file_editor_impl, sandbox_file_reader_impl, sandbox_guide_delivery_impl, sandbox_impl, sandbox_run_control_impl, template_format_impl, tool_provider_impl
imports: agent_config, agent_file_alias, agent_node_config, agent_session, commonmark_ext, dag_storage, dag_subgraph, file_paths, filesystem_ext
implements: sandbox, sandbox_file_reader, sandbox_file_editor, sandbox_run_control, sandbox_guide_delivery, tool_provider, template_format

## Purpose

The sandbox_asm assembly component aggregates file inspection, guarded editing, execution control, guide delivery, and tool dispatch services into the sandbox subsystem assembly.

Autonomous agents operating on source workspaces require isolated environments that combine file inspection tools, guarded in-place editors, progressive instruction delivery, and strict run completion verifiers. Without an integrated sandbox assembly, tools and validation services must be configured and wired independently across session boundaries, risking inconsistent argument conversion and permissive file write behaviors. The sandbox_asm assembly component unites concrete sandbox, tool provider, and verification modules into a cohesive subsystem, closing the sandbox and tool execution interfaces while declaring required dependencies on file aliases, configurations, and operating system storage boundaries.

**Out of scope:** The sandbox_asm assembly component does not parse Bazel build manifests, manage language model network connections, or schedule topological graph passes; these are handled by other components.

## Types and Behavior

The sandbox_asm assembly component aggregates the implementations of the sandbox, sandbox file reader, sandbox file editor, sandbox run control, sandbox guide delivery, tool provider, and template format interfaces, providing a unified assembly for agent session tools, workspace safety guardrails, instruction delivery, and run control verification.
