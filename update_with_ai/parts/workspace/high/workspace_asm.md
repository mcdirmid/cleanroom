<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:57Z
LAST_CHANGED: 2026-10-14T18:45:00Z
CHANGE: Add workspace_roles constituent
CODE_HASH: cb20155bbb61
SPEC_QA_AUDIT: 2026-10-15T19:43:57Z
-->

# workspace_asm assembly component

assembles: workspace_roles_impl, workspace_registry_impl, workspace_scaffold_impl, workspace_provision_impl, workspace_stub_impl, workspace_sync_impl
imports: agent_session, src_metadata
implements: workspace_roles, workspace_registry, workspace_scaffold, workspace_provision, workspace_stub, workspace_sync

## Purpose

The workspace_asm assembly component aggregates constituent workspace management implementation components, exposing complete role workspace provisioning, registration, and synchronization services.

Multi-role Cleanroom operations require coordinated wiring of registry persistence, permission-isolated provisioning, and bi-directional synchronization. Binding these components individually in consumer binaries duplicates initialization sequences and risks omitted services. The workspace_asm assembly component closes workspace interfaces and assembles all constituent implementation components into a unified assembly.

**Out of scope:** The workspace_asm assembly component does not define custom business logic, dispatch agent requests, or drive pipeline execution; these are handled by other components.

## Types and Behavior

The workspace_asm assembly component aggregates the implementations of the workspace registry, workspace provision, and workspace sync interfaces, providing a unified assembly for role workspace provisioning and synchronization.

The workspace assembly initializes its constituent implementations recursively and registers every singleton service with the agent session lifecycle tier.
