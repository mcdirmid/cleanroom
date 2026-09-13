# sandbox_asm assembly component

assembles: sandbox_change_summary_validator_impl, sandbox_file_editor_impl, sandbox_file_reader_impl, sandbox_guide_delivery_impl, sandbox_impl, sandbox_run_control_impl, template_format_impl, tool_provider_impl
imports: agent_config, agent_file_alias, agent_node_config, commonmark_ext, dag_storage, filesystem_ext
implements: sandbox, sandbox_file_reader, sandbox_file_editor, sandbox_run_control, sandbox_guide_delivery, sandbox_change_summary_validator, tool_provider, template_format

## Purpose

The sandbox_asm assembly component aggregates file inspection, guarded editing, execution control, guide delivery, change validation, and tool dispatch services into the sandbox subsystem assembly.

Autonomous agents operating on source workspaces require isolated environments that combine file inspection tools, guarded in-place editors, progressive instruction delivery, and strict run completion verifiers. Without an integrated sandbox assembly, tools and validation services must be configured and wired independently across session boundaries, risking inconsistent argument conversion and permissive file write behaviors. The sandbox_asm assembly component unites concrete sandbox, tool provider, and verification modules into a cohesive subsystem, closing the sandbox and tool execution interfaces while declaring required dependencies on file aliases, configurations, and operating system storage boundaries.

**Out of scope:** The sandbox_asm assembly component does not parse Bazel build manifests, manage language model network connections, or schedule topological graph passes; these are handled by other components.

## Types and Behavior

The *sandbox assembly* unites the concrete implementation components that realize agent session tools, workspace safety guardrails, instruction delivery, and run control verifiers. The assembly initializes its constituent implementation components and registers their singleton services with the system lifecycle prototype.

The sandbox assembly aggregates the following implementation components:

- The sandbox implementation from sandbox_impl, closing the sandbox interface to assemble startup tool executions, materialize templates, and expose session modification state.

- The sandbox file reader implementation from sandbox_file_reader_impl, closing the sandbox file reader interface to provide guarded file reading and regular expression pattern searching.

- The sandbox file editor implementation from sandbox_file_editor_impl, closing the sandbox file editor interface to provide text replacement and line update tools with template materialization.

- The sandbox run control implementation from sandbox_run_control_impl, closing the sandbox run control interface to provide advance, finish, fail, blame, and run tests execution control tools with sequential verification checks.

- The sandbox guide delivery implementation from sandbox_guide_delivery_impl, closing the sandbox guide delivery interface to parse markdown instructions and deliver progressive milestone steps.

- The sandbox change summary validator implementation from sandbox_change_summary_validator_impl, closing the sandbox change summary validator interface to evaluate net file modifications against reported change summaries.

- The tool provider implementation from tool_provider_impl, closing the tool provider interface to manage session tool registration, parameter conversion, and tool invocation dispatch.

- The template format implementation from template_format_impl, closing the template format interface to provide commonmark directive template formatting for missing files and read-only markdown files.
