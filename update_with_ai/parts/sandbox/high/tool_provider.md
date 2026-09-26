# tool_provider interface component

imports: agent_session

## Purpose

The tool_provider interface component enables agents to safely interact with environment capabilities through structured invocation boundaries and actionable outcome feedback.

Autonomous agent loops risk unpredictable deviations when environment actions are unconstrained or when failures lack informative feedback. Unstructured text interfaces force fragile parsing, whereas rigid crash behaviors prevent autonomous recovery. The tool_provider interface component establishes an extensible contract between the agent orchestration layer and concrete domain tooling, allowing external capabilities to be exposed hermetically while giving agents the structured feedback necessary to self-correct during multi-turn interactions.

**Out of scope:** The tool_provider interface component does not implement concrete domain tools, parse model output streams, supersede responses across conversation turns, or govern the agent turn loop; these are handled by other components.

## Types and Behavior

A *tool* is an action that an agent can call, having a name, a description, and a set of *tool parameters* so that an agent knows how to use the tool.

An agent session's *tool manager* installs tools for an agent session depending on the nature of the session, and provides installed tools. It is assumed that all installed tools in a tool manager have unique names.

Each tool parameter has a name and description so the agent can satisfy them, assuming all parameters of a tool have unique names. A parameter can be required, meaning the agent must provide a binding for it in a tool call, while an unrequired parameter can specify a *default value* used if omitted. A required parameter can also specify a *missing note* based on present parameters to inform the agent how to correct parameter omissions.

Each tool parameter has a *parameter type* describing the parameter's *python type* and *wire type*. A parameter type converts wire type values to python type values and provides feedback on failure. Wire types are limited to wire strings, wire integers, wire booleans, wire floats, wire lists, and wire dictionaries.

An *identity parameter type* has identical python and wire types with trivial conversion that cannot fail. A *list parameter type* converts lists using an element parameter type, while a *dictionary parameter type* converts dictionaries using key and element parameter types. A composite parameter type formed from other parameter types propagates all failures from constituent parameter types.

Via the tool manager, an agent can call tools by name with parameter bindings of wire type values. For each call, the tool manager resolves symbols, converts arguments, applies default values, and checks requirements, calling the tool with python type bindings and failing if the tool is not called properly.

A tool call produces a *tool response* providing tool output and communicating whether execution failed with diagnostic feedback or whether the conversation terminates. To manage conversation clutter across turns, a tool response can provide a *suppression key* that supersedes and hides prior conversation responses with the same key.

When a tool call can reliably predict a subsequent tool call that the agent is likely to make, a tool response can designate a *follow-up tool call*. A follow-up tool call specifies the next tool to call, values for its parameters, and reasoning text articulating from the agent's perspective why the next tool is being called.
