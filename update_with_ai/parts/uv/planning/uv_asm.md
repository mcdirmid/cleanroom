<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: a776ba85228c
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# uv_asm assembly component

imports: file_paths_impl, uv_manifest_loader_impl, uv_node_config_impl, uv_target_impl

## Intent

Aggregates workspace manifest loading, target resolution, file paths resolution, and node configuration implementations into a unified Cleanroom workspace subsystem assembly.

## Factored Contracts

### Contracts

- Assembles Cleanroom workspace subsystem implementations into the system lifecycle tier. [assemble_uv_subsystem]

## Grounding

### Knowledge Provisions

- Aggregated Cleanroom workspace subsystem assembly ready for orchestration. [uv_assembly_provision]

### Knowledge Requirements

- Integration of constituent Cleanroom services into lifecycle tier.
  - Grounded: [uv_assembly_provision]
