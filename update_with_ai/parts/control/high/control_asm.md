<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:56Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: e941aa09002b
SPEC_QA_AUDIT: 2026-10-15T19:43:56Z
-->

# control_asm assembly component

assembles: control_attribution_impl, control_coordinate_impl, control_submit_impl, control_verification_impl, control_work_scheduler_impl
imports: agent_config, agent_file_alias, agent_node_config, agent_session, dag_storage, dag_subgraph, src_metadata
implements: control_attribution, control_coordinate, control_submit, control_verification, control_work_scheduler

## Purpose

The control_asm assembly component aggregates session coordination, verification evaluation, work scheduling, submission gating, and defect attribution into a unified control package.

Complex multi-stage workflows require an integrated runtime environment where verification checkers, work schedulers, submit gates, and attribution handlers operate in seamless concert under a unified session coordinator. The control_asm assembly component binds these constituent implementations together, satisfying all public control interfaces and establishing the foundational execution control plane for Cleanroom.

**Out of scope:** The control_asm assembly component does not implement coordination logic, execute verification checks, or modify graph storage; these are handled by other components.

## Types and Behavior

The control_asm assembly component aggregates the implementations of control coordinate, control verification, control work scheduler, control submit, and control attribution, providing a unified assembly for the control plane.
