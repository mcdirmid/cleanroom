<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:56Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: e941aa09002b
SPEC_QA_AUDIT: 2026-10-15T19:43:56Z
-->

# control_asm assembly component

assembles: attribution_impl, coordinate_impl, submit_impl, verification_impl, work_scheduler_impl
imports: agent_config, file_alias, node_config, session, dag_storage, subgraph, src_metadata
implements: attribution, coordinate, submit, verification, work_scheduler

## Purpose

The control_asm assembly component aggregates session coordination, verification evaluation, work scheduling, submission gating, and defect attribution into a unified control package.

Complex multi-stage workflows require an integrated runtime environment where verification checkers, work schedulers, submit gates, and attribution handlers operate in seamless concert under a unified session coordinator. The control_asm assembly component binds these constituent implementations together, satisfying all public control interfaces and establishing the foundational execution control plane for Cleanroom.

**Out of scope:** The control_asm assembly component does not implement coordination logic, execute verification checks, or modify graph storage; these are handled by other components.

## Types and Behavior

The control_asm assembly component aggregates the implementations of control coordinate, control verification, control work scheduler, control submit, and control attribution, providing a unified assembly for the control plane.
