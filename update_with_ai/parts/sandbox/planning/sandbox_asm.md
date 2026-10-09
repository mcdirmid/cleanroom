<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-06T12:35:00Z
CHANGE: update to planning grounding format
CODE_HASH: 002f10b8584c
SPEC_QA_AUDIT: 2026-10-07T23:58:18Z
-->

# sandbox_asm assembly component

imports: sandbox_file_editor_impl, sandbox_file_reader_impl, sandbox_guide_delivery_impl, sandbox_impl, sandbox_run_control_impl, template_format_impl, tool_provider_impl

## Intent

Assembles file inspection, guarded editing, execution control, guide delivery, and tool dispatch constituents into the unified sandbox session assembly.

## Factored Contracts

### Contracts

- Assembles sandbox service implementations into the agent session lifecycle tier. [assemble_sandbox_services]

## Grounding

### Knowledge Provisions

- Aggregated sandbox session assembly ready for orchestration. [sandbox_assembly_provision]

### Knowledge Requirements

- Integration of constituent sandbox services into lifecycle tier.
  - Grounded: [sandbox_assembly_provision]
