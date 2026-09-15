# loop_asm assembly component

assembles: loop_guard_impl, loop_node_cleaner_impl, openai_conversation_impl, openai_driver_impl
imports: agent_config, agent_node_config, agent_storage, dag_storage, openai_config, openai_ext, runner_logger, sandbox, template_format, tool_provider
implements: dag_node_cleaner, loop_conversation, loop_driver, loop_guard

## Purpose

The loop_asm assembly component aggregates turn loop execution, prompt conversation history formatting, loop guard repetition tracking, and node cleaning orchestration into the loop subsystem assembly.

Autonomous problem solving requires binding language model completion pipelines, message history formatting, oscillatory loop protection, and graph message translation into a single coordinated execution engine. Without a unified loop assembly, callers must compose turn loops and node cleaners across fragmented boundaries, exposing orchestrators to lifecycle discrepancies and conversational drift. The loop_asm assembly component aggregates concrete loop implementation modules into an integrated subsystem, closing the loop driver, conversation, loop guard, and node cleaner interfaces while declaring required dependencies on storage, sandbox, and provider subsystems.

**Out of scope:** The loop_asm assembly component does not manage host file permissions, construct build manifests, or compute topological dependency schedules; these are handled by other components.

## Types and Behavior

The *loop assembly* unites the concrete implementation components that realize language model turn coordination, conversation history management, repetition detection, and node clean execution. The assembly initializes its constituent implementation components and registers their singleton services with the system lifecycle prototype.

The loop assembly aggregates the following implementation components:

- The loop driver implementation from openai_driver_impl, closing the loop driver interface to execute turn loops, dispatch tool calls, and evaluate termination outcomes.

- The conversation implementation from openai_conversation_impl, closing the loop conversation interface to format provider role structures and seed startup tool interactions.

- The loop guard implementation from loop_guard_impl, closing the loop guard interface to detect repetitive tool invocations and file edit oscillations.

- The node cleaner implementation from loop_node_cleaner_impl, closing the dag node cleaner interface to clean dirty nodes within session phases and dispatch propagating graph messages.
