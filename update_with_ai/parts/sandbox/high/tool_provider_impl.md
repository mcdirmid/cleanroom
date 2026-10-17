<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Canonicalize the missing note term and state wire value conversion declaratively
CODE_HASH: 15002f30f1d3
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# tool_provider_impl implementation component

imports: file_alias
implements: tool_provider

## Purpose

The tool_provider_impl implementation component realizes centralized tool execution, tool discovery services, and primitive wire type converters for agent sessions.

Autonomous agent workflows require executing tools with wire-type arguments supplied by the agent without coupling individual tools to string deserialization or dynamic lookup mechanics. Decentralized argument translation risks inconsistent parsing, unhandled type conversions, and fragmented error handling across sessions. The tool_provider_impl implementation component establishes an in-memory session registry that matches tools by name, translates wire type arguments into tool-expected actual types using parameter types defined on tool parameters, and returns structured responses for agent orchestration.

**Out of scope:** The tool_provider_impl implementation component does not implement concrete domain tools, govern the agent turn loop, or parse model output streams; these are handled by other components.

## Types and Behavior

The tool manager maintains the tools installed during an agent session, and exposes installed tools so the agent knows which tools it can execute.

Executing a tool by name with wire parameter bindings converts wire arguments into actual parameter bindings and executes the matching tool. The tool manager binds the default value of a parameter that is not required when an argument for that parameter is omitted and a default value is configured.

Execution fails if:

- No installed tool matches the requested name.

- A name is supplied in parameter bindings that does not match a known parameter of the tool, and reminds the agent that only declared parameters of the tool can be provided.

- An argument is not supplied for a required parameter of the tool, incorporating the missing note of that parameter evaluated against the supplied parameter names when configured, and reminding the agent that required parameters of the tool must be supplied.

On successful argument resolution, the tool manager executes the tool with the resolved actual parameter bindings and returns the response produced by the tool.

Executing a tool with argument mappings executes the tool by name with wire parameter bindings.

The identity parameter type converts wire values into identical actual values for its target type.

The list parameter type converts wire type lists into actual type lists by converting each element with its item parameter type.

The mapping parameter type converts wire type mappings into actual type mappings by converting each key with its key parameter type and each value with its value parameter type.

The alias manager type converts a wire string to a file alias by delegating to the session alias manager to alias.
