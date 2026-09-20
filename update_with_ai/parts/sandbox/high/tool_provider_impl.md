# tool_provider_impl implementation component

implements: tool_provider

## Purpose

The tool_provider_impl implementation component realizes centralized tool execution, tool discovery services, and primitive wire type converters for agent sessions.

Autonomous agent workflows require executing tools with wire-type arguments supplied by the agent without coupling individual tools to string deserialization or dynamic lookup mechanics. Decentralized argument translation risks inconsistent parsing, unhandled type conversions, and fragmented error handling across sessions. The tool_provider_impl implementation component establishes an in-memory session registry that matches tools by name, translates wire type arguments into tool-expected actual types using parameter types defined on tool parameters, and returns structured responses for agent orchestration.

**Out of scope:** The tool_provider_impl implementation component does not implement concrete domain tools, govern the agent turn loop, or parse model output streams; these are handled by other components.

## Types and Behavior

The tool manager maintains tools installed during an agent session, and exposes installed tools to inform the agent of what tools it can execute.

Executing a tool by name with wire parameter bindings converts wire arguments into actual parameter bindings and delegates execution to the matching tool. When an argument is omitted for a parameter that is not required and has a default value, the tool manager binds the default value as the actual parameter value.

Execution fails if:

- No installed tool matches the requested name.

- A name is supplied in parameter bindings that does not match known parameters of the tool, and reminds the agent that only declared parameters of the tool can be provided.

- Any required parameter of the tool is omitted, and reminds the agent that required parameters of the tool must be supplied.

On successful argument resolution, the tool manager executes the tool with the resolved actual parameter bindings and returns the response produced by the tool.

Executing a tool with arguments converts raw argument mappings into wire parameter bindings and delegates to tool execution by name.

Creating a tool callable constructs a callable function with parameter signatures derived from the tool parameters, executes the tool with supplied arguments upon invocation, and returns the response content combined with reminders when guidance is present.

The identity parameter type converts wire type values to produce identical actual values for its target type.

The list parameter type converts wire type lists to actual type lists by converting each element with its item parameter type.

The dictionary parameter type converts wire type dictionaries to actual type dictionaries by converting each key with its key parameter type and each value with its value parameter type.
