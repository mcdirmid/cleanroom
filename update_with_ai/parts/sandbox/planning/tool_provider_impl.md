<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-11T03:10:51Z
CHANGE: Add default value binding, unknown tool failure, and response return to tool execution contracts
CODE_HASH: 078e8209cfcd
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# tool_provider_impl implementation component

## Intent

Autonomous agent workflows require executing tools with wire-type arguments supplied by the agent without coupling individual tools to string deserialization or dynamic lookup mechanics. Decentralized argument translation risks inconsistent parsing, unhandled type conversions, and fragmented error handling across sessions. The tool_provider_impl implementation component establishes an in-memory session registry that matches tools by name, translates wire type arguments into tool-expected actual types using parameter types defined on tool parameters, and returns structured responses for agent orchestration.

To facilitate robust interaction across dynamic agent environments, the implementation provides specialized entry points that accept argument mappings and validate parameter declarations before dispatch. The implementation defends model boundaries against undeclared parameter keys and missing mandatory parameters, providing explicit diagnostic reminders so that autonomous agents can self-correct malformed calls in subsequent turns.

## Factored Contracts

### Contracts

- Executing a tool by name invokes it with converted actual parameter bindings and returns the response the tool produces. [exec_by_name]
- Executing a tool with argument mappings delegates execution to execute by name with wire parameter bindings. [delegate_exec_with_args]
- The tool manager binds the default value of a non-required parameter when an argument for that parameter is omitted and a default value is configured. [bind_default_value_when_omitted]
- Tool execution fails when no installed tool matches the requested name. [unknown_tool_fails]
- Tool execution fails when a parameter binding name does not match known parameters of the tool. [unknown_param_fails]
- When an unknown parameter name is supplied, failure feedback reminds the agent that only declared parameters of the tool can be provided. [unknown_param_reminder]
- When a required parameter argument is omitted, failure feedback reminds the agent that required parameters of the tool must be supplied. [omitted_required_reminder]

### Woven Contracts

- When executing a tool with argument mappings, the tool is executed by name with wire parameter bindings. [delegate_exec_with_args, tool_provider: [call_wire_bindings, call_by_name]]
- When parameter bindings request a name that matches no installed tool, execution fails. [unknown_tool_fails, tool_provider: [call_by_name, call_improper_fails, failed_call_feedback]]
- When a call omits a non-required parameter configuring a default value, the default value is bound for the call. [bind_default_value_when_omitted, tool_provider: [apply_defaults, call_with_python_bindings]]
- When parameter bindings contain a name that does not match known parameters of the tool, execution fails with feedback citing the unknown parameter and reminding the agent that only declared parameters of the tool can be provided. [unknown_param_fails, unknown_param_reminder, tool_provider: [provide_tool_params, call_by_name, resolve_symbols, call_improper_fails, failed_call_feedback]]
- When a call omits a required parameter configuring a missing note evaluated against present parameters, execution fails with feedback citing the missing parameter, the evaluated missing note, and reminding the agent that required parameters of the tool must be supplied. [omitted_required_reminder, tool_provider: [check_requirements, call_improper_fails, failed_call_feedback]]
- When a call omits a required parameter lacking a configured missing note, execution fails with feedback citing the missing parameter and reminding the agent that required parameters of the tool must be supplied. [omitted_required_reminder, tool_provider: [check_requirements, call_improper_fails, failed_call_feedback]]

## Grounding

### Knowledge Provisions

- Private dictionary mapping tool names to installed tools. [private_tool_storage]
- Mutation capability to insert tools into private dictionary. [private_tool_mutation]

### Inherited Deferred Requirements

- Access to backing collection storing installed tools.
  - Grounded: [private_tool_storage]
- Capability to register and mutate installed tools in storage.
  - Grounded: [private_tool_mutation]

### Knowledge Requirements

- Execution of tools by name with parameter binding conversion and diagnostic error handling.
  - Grounded: [private_tool_storage, tool_provider: [wire_value_conversion, tool_execution_capability, tool_response_generation]]
