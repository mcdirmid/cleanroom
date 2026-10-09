<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-08T12:55:00Z
LAST_CHANGED: 2026-10-08T12:55:00Z
CHANGE: assemble workspace_tool_impl
CODE_HASH: df55453dda02
SPEC_QA_AUDIT: 2026-10-08T12:55:00Z
-->

# cleanroom_asm assembly component

imports: bazel_openai_loop_asm, control_asm, file_paths_impl, tools_asm, workspace_asm, workspace_tool_impl

## Intent

Assembles all Cleanroom subsystems including the Bazel OpenAI loop, session control, file paths, developer tools, role workspace management, and the workspace tool runner into the comprehensive Cleanroom root system assembly.

## Factored Contracts

### Contracts

- Assembles all constituent Cleanroom subsystems into the master root system assembly. [assemble_cleanroom_system]

## Grounding

### Knowledge Provisions

- Aggregated Cleanroom master root system assembly ready for unified execution and verification. [cleanroom_assembly_provision]

### Knowledge Requirements

- Integration of constituent subsystem assemblies and standalone implementations into the master system.
  - Grounded: [cleanroom_assembly_provision]
