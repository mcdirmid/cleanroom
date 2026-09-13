# agent_asm assembly component

assembles: agent_loop_guard_impl, agent_node_cleaner_impl, openai_conversation_impl, openai_driver_impl
imports: agent_storage, dag_storage, model_config, node_config, runner_logger, sandbox, tool_provider, openai_ext
implements: agent_conversation, agent_driver, agent_loop_guard, dag_node_cleaner

## Purpose

The agent_asm assembly component aggregates turn loop execution, prompt conversation history formatting, loop guard repetition tracking, and node cleaning orchestration into the agent subsystem assembly.

Autonomous problem solving requires binding language model completion pipelines, message history formatting, oscillatory loop protection, and graph message translation into a single coordinated execution engine. Without a unified agent assembly, callers must compose turn loops and node cleaners across fragmented boundaries, exposing orchestrators to lifecycle discrepancies and conversational drift. The agent_asm assembly component aggregates concrete agent implementation modules into an integrated subsystem, closing the agent driver, conversation, loop guard, and node cleaner interfaces while declaring required dependencies on storage, sandbox, and provider subsystems.

**Out of scope:** The agent_asm assembly component does not manage host file permissions, construct build manifests, or compute topological dependency schedules; these are handled by other components.

## Types and Behavior

The *agent assembly* unites the concrete implementation components that realize language model turn coordination, conversation history management, repetition detection, and node clean execution. The assembly initializes its constituent implementation components and registers their singleton services with the system lifecycle prototype.

The agent assembly aggregates the following implementation components:

- The agent driver implementation from openai_driver_impl, closing the agent driver interface to execute turn loops, dispatch tool calls, and evaluate termination outcomes.

- The conversation implementation from openai_conversation_impl, closing the agent conversation interface to format provider role structures and seed startup tool interactions.

- The agent loop guard implementation from agent_loop_guard_impl, closing the agent loop guard interface to detect repetitive tool invocations and file edit oscillations.

- The node cleaner implementation from agent_node_cleaner_impl, closing the dag node cleaner interface to clean dirty nodes within session phases and dispatch propagating graph messages.
