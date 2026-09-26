# tool_provider_impl implementation component

implements: tool_provider

## Assumptions and Requirements

### Requirements

1. Executing a tool by name fails if no installed tool matches the requested name.
2. Executing a tool by name fails if a parameter name does not match any parameter of the tool, and reminds the agent that only declared parameters of the tool can be provided.
3. Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, incorporating the parameter's missing message function evaluated with the set of supplied parameter names when configured, and reminds the agent that required parameters of the tool must be supplied.
4. When an argument is omitted for a parameter that is not required and has a default value, the tool manager binds the default value as the actual parameter value.
5. When parameter mappings are successfully resolved, executing a tool by name executes the matching tool with the resolved actual parameter bindings and returns the tool's response.
6. Executing a tool with arguments converts raw argument mappings into wire parameter bindings and executes the tool by name.

## Grounding Facts

### Knowledge Needed

- Installed tools map.
- Parameter declarations.
- Raw argument mappings and wire bindings.

### Actions Needed

- Match tool name against installed tools.
- Validate parameter names and check required parameters.
- Bind default values for omitted optional parameters.
- Convert raw arguments and execute matching tool.
- Return structured tool response.
