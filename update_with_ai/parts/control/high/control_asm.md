<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 7594b8477adf
-->

# control_asm assembly component

assembles: control_coordinate_impl, control_verification_impl, control_work_scheduler_impl, control_submit_impl, control_attribution_impl, src_metadata_impl
imports: agent_session, dag_storage, dag_subgraph, agent_node_config, agent_file_alias, agent_config, src_metadata_ext
implements: control_coordinate, control_verification, control_work_scheduler, control_submit, control_attribution, src_metadata

## Purpose

The control_asm assembly component aggregates session coordination, verification evaluation, work scheduling, submission gating, and defect attribution into a unified control package.

Complex multi-stage workflows require an integrated runtime environment where verification checkers, work schedulers, submit gates, and attribution handlers operate in seamless concert under a unified session coordinator. The control_asm assembly component binds these constituent implementations together, satisfying all public control interfaces and establishing the foundational execution control plane for Cleanroom.

**Out of scope:** The control_asm assembly component contains no operational logic or branching code; these are handled by other components.

## Types and Behavior

The control_asm assembly component aggregates the implementations of control coordinate, control verification, control work scheduler, control submit, control attribution, and src metadata, providing a unified assembly for the control plane.
