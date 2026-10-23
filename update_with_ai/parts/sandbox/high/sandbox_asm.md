# sandbox_asm assembly component

assembles: file_editor_impl, file_reader_impl, guide_delivery_impl, run_control_impl, submission_impl, template_format_impl, tool_provider_impl
imports: agent_config, file_alias, node_config, session, commonmark_ext, dag_storage, subgraph, file_paths, filesystem_ext
implements: file_reader, file_editor, run_control, submission, guide_delivery, tool_provider, template_format

## Purpose

The sandbox_asm assembly component aggregates file inspection, guarded editing, execution control, outcome submission, guide delivery, and tool dispatch services into the sandbox subsystem assembly.

Autonomous agents operating on source workspaces require isolated environments that combine file inspection tools, guarded in-place editors, progressive instruction delivery, and strict run completion verifiers. Without an integrated sandbox assembly, tools and validation services must be configured and wired independently across session boundaries, risking inconsistent argument conversion and permissive file write behaviors. The sandbox_asm assembly component unites concrete sandbox, tool provider, and verification modules into a cohesive subsystem, closing the sandbox and tool execution interfaces while declaring required dependencies on file aliases, configurations, and operating system storage boundaries.

**Out of scope:** The sandbox_asm assembly component does not parse package manifests, manage language model network connections, or schedule topological graph passes; these are handled by other components.

## Types and Behavior

The sandbox_asm assembly component aggregates the implementations of the sandbox file reader, sandbox file editor, sandbox run control, sandbox submission, sandbox guide delivery, tool provider, and template format interfaces, providing a unified assembly for agent session tools, workspace safety guardrails, instruction delivery, and run control verification.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:57Z
LAST_CHANGED: 2026-10-14T18:30:00Z
CHANGE: Assemble submission_impl and implement submission
SPEC_QA_AUDIT: 2026-10-15T19:43:57Z
-->
