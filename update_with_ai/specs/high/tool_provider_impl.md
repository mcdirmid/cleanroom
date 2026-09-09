# tool_provider_impl implementation component

implements: tool_provider

## Purpose

The tool_provider_impl implementation component realizes centralized tool execution, tool discovery services, and primitive wire type converters for agent sessions.

Autonomous agent workflows require executing tools with wire-type arguments supplied by the agent without coupling individual tools to string deserialization or dynamic lookup mechanics. Decentralized argument translation risks inconsistent parsing, unhandled type conversions, and fragmented error handling across sessions. The tool_provider_impl implementation component establishes an in-memory session registry that matches tools by name, translates wire type arguments into tool-expected actual types using parameter converters defined on tool parameters, and returns structured responses for agent orchestration.

**Out of scope:** The tool_provider_impl implementation component does not implement concrete domain tools, govern the agent turn loop, or parse model output streams; these are handled by other components.

## Types and Behavior

The tool manager maintains tools installed during an agent session, and exposes installed tools to inform the agent of what tools it can execute.

Executing a tool by name with wire parameter bindings converts wire arguments into actual parameter bindings and delegates execution to the matching tool. Execution fails if:

- No installed tool matches the requested name.

- A name is supplied in parameter bindings that does not match known parameters of the tool.

- Any required parameter of the tool is omitted.

On successful argument resolution, the tool manager executes the tool with the resolved actual parameter bindings and returns the response produced by the tool.

The string parameter converter, integer parameter converter, and boolean parameter converter convert wire type string, integer, and boolean values to produce identical actual values.
