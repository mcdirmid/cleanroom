<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: restore core constituents
CODE_HASH: fdf0034aca28
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# workspace_asm assembly component

assembles: workspace_registry_impl, workspace_provision_impl, workspace_sync_impl, workspace_work_impl
imports: agent_session, control_work_scheduler, src_metadata
implements: workspace_registry, workspace_provision, workspace_sync, workspace_work

## Purpose

The workspace_asm assembly component aggregates constituent workspace management implementation components, exposing complete role workspace provisioning, synchronization, and work queue services.

Multi-role Cleanroom operations require coordinated wiring of registry persistence, permission-isolated provisioning, bi-directional synchronization, and work discovery. Binding these components individually in consumer binaries duplicates initialization sequences and risks omitted services. The workspace_asm assembly component closes workspace interfaces and assembles all constituent implementation components into a unified assembly.

**Out of scope:** The workspace_asm assembly component does not define custom business logic, dispatch agent requests, or drive pipeline execution; these are handled by other components.

## Types and Behavior

The workspace_asm assembly component aggregates the implementations of the workspace registry, workspace provision, workspace sync, and workspace work interfaces, providing a unified assembly for role workspace provisioning, synchronization, and work discovery.

The workspace assembly initializes its constituent implementations recursively and registers every singleton service with the agent session lifecycle tier.
