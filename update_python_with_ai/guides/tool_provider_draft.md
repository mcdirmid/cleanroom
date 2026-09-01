# tool_provider

## Purpose

Standardizes tool discovery, execution, and outcomes for agent interactions, defining how tools describe themselves, how execution produces results or failure feedback, and how termination is signaled.

## Types

- A *tool provider* is a provider of available *tools*
- A *tool* performs an action described by *tool metadata* when executed with arguments
- A *tool metadata* describes a *tool*'s name, purpose, and expected arguments to an agent
- A *tool result* is the successful outcome of executing a *tool*, carrying produced content and optional guidance
- A *tool failure* is an execution outcome signaling that a *tool* could not be executed or complete, carrying feedback to guide the calling agent toward recovery
- A *termination outcome* is a *tool result* communicating that execution has completed

## Behavior

- A *tool provider* provides a list of available *tools*.
- A *tool* provides *tool metadata* describing its name, purpose, and expected arguments.
- A *tool* is executed with arguments matching its *tool metadata*.
- When executing a *tool* encounters invalid arguments, a policy violation, or an unmet prerequisite, execution produces a *tool failure* without modifying state.
- A *tool failure* provides actionable feedback so the calling agent can self-correct and continue.
- Executing a *tool* produces a *tool result*, which may be a *termination outcome*.
- A *tool result* carries the content produced by the *tool* and optional producer-generated guidance for the agent.
- A *termination outcome* is terminal and atomic; once produced, execution concludes and no further *tool results* are produced.
