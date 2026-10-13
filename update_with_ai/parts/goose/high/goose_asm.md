<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T09:50:00Z
CHANGE: author goose_asm assembly specification
CODE_HASH: 5aa8351578ef
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# goose_asm assembly component

assembles: goose_workspace_impl, goose_harness_impl
imports: agent_session, goose_ext, subagent_coordinator, workspace_work
implements: goose_workspace, goose_harness

## Purpose

The goose_asm assembly component aggregates constituent Goose workspace and harness implementation components, exposing complete Goose platform integration services.

Integrating Cleanroom with Goose requires coordinated assembly of workspace boundary configuration and harness adapter execution. The goose_asm assembly component closes Goose interfaces and assembles constituent implementations into a unified assembly.

**Out of scope:** The goose_asm assembly component does not define custom business logic, dispatch agent requests, or drive pipeline execution; these are handled by other components.

## Types and Behavior

The goose_asm assembly component aggregates the implementations of the goose workspace and goose harness interfaces, providing a unified assembly for Goose platform integration.

The goose assembly initializes its constituent implementations recursively and registers every singleton service with the agent session lifecycle tier.
