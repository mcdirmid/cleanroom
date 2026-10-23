# loop_asm assembly component

assembles: guard_impl, node_cleaner_impl
imports: node_config, node_storage, dag_storage, subgraph, conversation, driver, logger, src_metadata, tool_provider
implements: cleaner, guard, node_cleaner

## Purpose

The loop_asm assembly component aggregates loop guard repetition tracking, subgraph iteration, and node cleaning orchestration into the loop subsystem assembly.

Autonomous problem solving requires binding message history formatting, oscillatory loop protection, and graph message translation into a single coordinated execution engine. Without a unified loop assembly, callers must compose turn loops and node cleaners across fragmented boundaries, exposing orchestrators to lifecycle discrepancies and conversational drift. The loop_asm assembly component aggregates concrete loop implementation modules into an integrated subsystem, closing the loop cleaner, loop guard, and node cleaner interfaces while declaring required dependencies on storage, subgraph, sandbox, and provider subsystems.

**Out of scope:** The loop_asm assembly component does not manage host file permissions, construct build manifests, or compute topological dependency schedules; these are handled by other components.

## Types and Behavior

The loop_asm assembly component aggregates the implementations of the loop cleaner, loop guard, and loop node cleaner interfaces, providing a unified assembly for repetition detection, subgraph cleaning iteration, and node clean execution.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:57Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Reduce the assembly narrative to a single structural sentence and remove constituent naming from prose
SPEC_QA_AUDIT: 2026-10-15T19:43:57Z
-->
