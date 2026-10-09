<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-08T12:55:00Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: restore core constituents
CODE_HASH: ece4e8c7ecce
-->

# workspace_asm assembly component

assembles: workspace_registry_impl, workspace_provision_impl, workspace_sync_impl, workspace_work_impl
imports: agent_session, control_work_scheduler, src_metadata
implements: workspace_registry, workspace_provision, workspace_sync, workspace_work

## Purpose

The workspace_asm assembly component aggregates constituent workspace management implementation components, exposing complete role workspace provisioning, synchronization, and work queue services.

Decentralized multi-role Cleanroom operations require coordinated wiring of registry persistence, permission-isolated provisioning, bi-directional synchronization, and work discovery. Binding these components individually in consumer binaries duplicates initialization sequences and risks omitted services. The workspace_asm assembly component closes workspace interfaces and assembles all constituent implementation components into a unified assembly.

**Out of scope:** The workspace_asm assembly component does not define custom business logic, dispatch agent requests, or drive pipeline execution; these are handled by other components.

## Types and Behavior

The workspace assembly provides complete realization of workspace services across the agent session tier.

Constituent implementations assembled include:

- The workspace registry implementation, resolving role definitions, computing sanitized directory paths, and persisting active workspace descriptors.

- The workspace provisioner implementation, commissioning isolated directory trees, applying read-only attributes to upstream contracts, deploying zipapp runner tools in `bin/`, and decommissioning clean workspaces.

- The workspace synchronizer implementation, pulling updated contracts from canonical repositories, harvesting verified changes with in-band hash checks, refreshing system files, and flushing buffered blame feedback.

- The workspace work manager implementation, discovering ready and blocked tasks using dynamic role precedence across directory scopes and tracking pending targets.
