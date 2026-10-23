# antigravity_asm assembly component

assembles: antigravity_coordinator_impl, antigravity_harness_impl
imports: session, antigravity_ext, subagent_coordinator, role_registry
implements: antigravity_coordinator, antigravity_harness, antigravity_workspace

## Purpose

The antigravity_asm assembly component aggregates constituent Google Antigravity workspace, coordinator, and harness implementation components, exposing complete Antigravity platform integration services.

Integrating Cleanroom with Google Antigravity requires coordinated assembly of workspace boundary provisioning, coordinator skill generation, and harness adapter execution. The antigravity_asm assembly component closes Antigravity interfaces and assembles constituent implementations into a unified assembly.

**Out of scope:** The antigravity_asm assembly component does not define custom business logic, dispatch agent requests, or drive pipeline execution; these are handled by other components.

## Types and Behavior

The antigravity_asm assembly component aggregates the implementations of the antigravity workspace, antigravity coordinator, and antigravity harness interfaces, providing a unified assembly for Google Antigravity integration.

The antigravity assembly initializes its constituent implementations recursively and registers every singleton service with the agent session lifecycle tier.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:56Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_asm assembly specification
SPEC_QA_AUDIT: 2026-10-15T19:43:56Z
-->
