# tool_provider interface component

imports: agent_session

## Intent

Autonomous agent loops require structured boundaries to interact safely with environment capabilities. Free-form text interfaces force fragile parsing and invite unpredictable agent deviations, while rigid crash behaviors prevent autonomous error recovery. The tool_provider interface component establishes an extensible contract between the agent orchestration layer and concrete domain tooling.

By formalizing tool schemas with explicit parameter descriptions, agents can discover and satisfy invocation requirements without guessing. Wire types decouple external serialized payloads from internal Python domain types, intercepting malformed inputs before tool execution begins. When invocations are malformed, structured diagnostic feedback provides the necessary context for the agent to self-correct in subsequent turns.

To preserve agent context window capacity across multi-turn interactions, responses can designate suppression keys to prune repetitive or superseded outputs from conversation history. For predictable multi-step workflows, responses can designate follow-up tool calls with first-person reasoning to drive immediate sequential execution without turn latency.

## Factored Contracts

### Typing

- A tool has a name.
- A tool has a description.
- A tool has tool parameters.
- A tool parameter has a name.
- A tool parameter has a description.
- A tool parameter specifies a parameter type.
- A tool parameter can be designated as required.
- A non-required parameter can specify a default value.
- A required parameter can specify a missing note based on present parameters.
- Wire types are limited to wire strings, wire integers, wire booleans, wire floats, wire lists, and wire mappings.
- An identity parameter type specifies that the wire type matches the python type.
- Wired parameter bindings specify wire type values for parameter names.
- Action parameter bindings specify actual values for tool parameters.
- A tool response provides tool output.
- A tool response communicates whether the conversation terminates.
- A tool response can provide a suppression key.
- A tool response can designate a follow-up tool call.
- A follow-up tool call specifies the next tool to call.
- A follow-up tool call specifies wired parameter bindings for the next tool.
- A follow-up tool call specifies reasoning text articulating from the agent's perspective why the next tool is called.
- A parameter conversion error indicates that a wire value cannot be converted to the actual type.

### Contracts

- An agent session specifies tools to install based on the nature of the session. [session_tools_spec]
- An agent supplies wired parameter bindings when calling a tool. [call_wire_bindings]
- A tool provides tool parameters as a mapping. [provide_tool_params]
- Wired parameter bindings map parameter names to wire type values. [map_wire_bindings]
- Action parameter bindings map tool parameters to actual values. [map_action_bindings]
- An agent session's tool manager installs tools for the agent session. [install_tools]
- A parameter type converts wire type values to python type values. [convert_wire_val]
- An identity parameter type converts wire values to python values without failure. [convert_identity]
- A list parameter type converts lists using an element parameter type. [convert_list]
- A mapping parameter type converts mapping keys with a key parameter type. [convert_mapping_keys]
- A mapping parameter type converts mapping values with an element parameter type. [convert_mapping_vals]
- A tool manager provides installed tools as a mapping. [provide_installed_tools]
- A tool call produces a tool response. [call_produces_response]
- A tool response can provide a suppression key to supersede prior conversation responses with the same key. [supersede_by_key]
- A tool response can designate a follow-up tool call predicting the agent's next action. [predict_follow_up]
- A parameter type raises a parameter conversion error on conversion failure. [convert_failure_error]
- A composite parameter type formed from constituent parameter types propagates a constituent conversion failure. [composite_failure_propagate]
- A tool manager calls tools by name. [call_by_name]
- For each call, the tool manager resolves symbols. [resolve_symbols]
- For each call, the tool manager converts arguments. [convert_arguments]
- When argument conversion raises a parameter conversion error, the tool manager fails the call with diagnostic feedback. [catch_conversion_error]
- For each call, the tool manager applies default values for omitted non-required parameters. [apply_defaults]
- For each call, the tool manager checks parameter requirements. [check_requirements]
- For each call, the tool manager calls the tool with action parameter bindings. [call_with_python_bindings]
- A tool call fails when a tool is not called properly. [call_improper_fails]
- A tool call fails when tool-specific execution conditions fail. [exec_condition_fails]
- A failed tool call communicates diagnostic feedback in the tool response. [failed_call_feedback]

## Woven Contracts

- When installing a tool, name collision handling is out of scope. [install_tools]
- When a response specifies a suppression key, prior conversation turns with the same key are hidden. [call_produces_response, supersede_by_key]
- When a subsequent call can be reliably predicted, the response designates the next tool call with wired parameter bindings and agent reasoning. [call_produces_response, predict_follow_up]
- Identity parameter conversion never raises a parameter conversion error. [convert_identity, convert_failure_error]
- When calling a tool whose name does not match any installed tool, the call fails with feedback citing the unknown tool and listing installed tools. [provide_installed_tools, call_by_name, call_improper_fails, failed_call_feedback]
- When a call omits a required parameter specifying a missing note evaluated against present parameters, the call fails with feedback citing the missing parameter and missing note. [check_requirements, call_improper_fails, failed_call_feedback]
- When a call omits a required parameter lacking a missing note, the call fails with feedback citing the missing parameter. [check_requirements, call_improper_fails, failed_call_feedback]
- When a call omits a non-required parameter specifying a default value, the default value is bound for the call. [apply_defaults, call_with_python_bindings]
- When wire conversion fails for a parameter, the tool call fails with feedback citing the parameter name and the conversion failure feedback. [convert_wire_val, convert_failure_error, convert_arguments, catch_conversion_error, call_improper_fails, failed_call_feedback]
- When a constituent conversion fails in a composite type, conversion fails propagating that constituent's failure. [convert_list, convert_mapping_keys, convert_mapping_vals, convert_failure_error, composite_failure_propagate]
- When all parameter symbols resolve, required parameters are present, defaults are applied, and wire conversions succeed, the tool is called with action parameter bindings and returns its tool response. [call_wire_bindings, convert_wire_val, call_produces_response, resolve_symbols, convert_arguments, apply_defaults, check_requirements, call_with_python_bindings]
- When tool-specific execution conditions fail, failure status is indicated in the tool response with diagnostic feedback. [call_produces_response, exec_condition_fails, failed_call_feedback]
