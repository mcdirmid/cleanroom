<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Reduce the assembly narrative to a single structural sentence and remove constituent naming from prose
CODE_HASH: 9bac1278e045
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# loop_asm assembly component

assembles: loop_cleaner_impl, loop_guard_impl, loop_node_cleaner_impl, openai_conversation_impl, openai_driver_impl
imports: agent_config, agent_node_config, agent_storage, dag_storage, dag_subgraph, json_ext, openai_config, openai_ext, runner_logger, sandbox, tool_provider
implements: loop_cleaner, loop_conversation, loop_driver, loop_guard, loop_node_cleaner

## Purpose

The loop_asm assembly component aggregates turn loop execution, prompt conversation history formatting, loop guard repetition tracking, subgraph iteration, and node cleaning orchestration into the loop subsystem assembly.

Autonomous problem solving requires binding language model completion pipelines, message history formatting, oscillatory loop protection, and graph message translation into a single coordinated execution engine. Without a unified loop assembly, callers must compose turn loops and node cleaners across fragmented boundaries, exposing orchestrators to lifecycle discrepancies and conversational drift. The loop_asm assembly component aggregates concrete loop implementation modules into an integrated subsystem, closing the loop cleaner, loop driver, conversation, loop guard, and node cleaner interfaces while declaring required dependencies on storage, subgraph, sandbox, and provider subsystems.

**Out of scope:** The loop_asm assembly component does not manage host file permissions, construct build manifests, or compute topological dependency schedules; these are handled by other components.

## Types and Behavior

The loop_asm assembly component aggregates the implementations of the loop cleaner, loop conversation, loop driver, loop guard, and loop node cleaner interfaces, providing a unified assembly for language model turn coordination, conversation history management, repetition detection, subgraph cleaning iteration, and node clean execution.
