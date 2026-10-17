<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:56Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_asm assembly specification
CODE_HASH: 6407b4266acb
SPEC_QA_AUDIT: 2026-10-15T19:43:56Z
-->

# dsh_asm assembly component

assembles: dsh_workspace_impl, dsh_telemetry_impl, dsh_harness_impl
imports: session, dsh_ext, subagent_coordinator, work
implements: dsh_workspace, dsh_telemetry, dsh_harness

## Purpose

The dsh_asm assembly component aggregates constituent DeepSeek Harness workspace and harness implementation components, exposing complete DeepSeek Harness platform integration services.

Integrating Cleanroom with DeepSeek Harness requires coordinated assembly of workspace boundary configuration and harness adapter execution. The dsh_asm assembly component closes DeepSeek Harness interfaces and assembles constituent implementations into a unified assembly.

**Out of scope:** The dsh_asm assembly component does not define custom business logic, dispatch agent requests, or drive pipeline execution; these are handled by other components.

## Types and Behavior

The dsh_asm assembly component aggregates the implementations of the dsh workspace and dsh harness interfaces, providing a unified assembly for DeepSeek Harness platform integration.

The dsh assembly initializes its constituent implementations recursively and registers every singleton service with the agent session lifecycle tier.
