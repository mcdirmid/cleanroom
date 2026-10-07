<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 0bd1242f65d1
-->

# bazel_asm assembly component

imports: bazel_manifest_loader_impl, bazel_node_config_impl, bazel_storage_impl, bazel_target_impl, file_paths_impl

## Intent

Aggregates workspace manifest loading, dependency graph storage, message persistence, target resolution, file paths resolution, and node configuration implementations into a unified Bazel workspace subsystem assembly.

## Factored Contracts

### Contracts

- Assembles Bazel workspace subsystem implementations into the system lifecycle tier. [assemble_bazel_subsystem]

## Grounding

### Knowledge Provisions

- Aggregated Bazel workspace subsystem assembly ready for orchestration. [bazel_assembly_provision]

### Knowledge Requirements

- Integration of constituent Bazel services into lifecycle tier.
  - Grounded: [bazel_assembly_provision]
