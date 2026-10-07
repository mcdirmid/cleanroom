<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 75270be71a06
-->

# control_asm assembly component

imports: control_coordinate_impl, control_verification_impl, control_work_scheduler_impl, control_submit_impl, control_attribution_impl, src_metadata_impl

## Intent

Assembles session coordination, verification evaluation, work scheduling, submission gating, defect attribution, and source metadata constituents into the unified control package.

## Factored Contracts

### Contracts

- Assembles control service implementations into the agent session lifecycle tier. [assemble_control_services]

## Grounding

### Knowledge Provisions

- Aggregated control session assembly ready for orchestration. [control_assembly_provision]

### Knowledge Requirements

- Integration of constituent control services into lifecycle tier.
  - Grounded: [control_assembly_provision]
