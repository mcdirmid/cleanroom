# tool_provider interface component

imports: agent_session

## Assumptions and Requirements

### Assumptions

1. All installed tools in a tool manager have unique names.
2. All parameters of a tool have unique names.

### Requirements

3. Tools are installed via an agent session's tool manager.
   - (woven with assumption [1]): The tool to install must have a name distinct from all previously installed tools.
4. The tool manager can provide a list of installed tools.
5. A parameter can be required, meaning the agent must provide a binding for it in a proper tool call.
6. A non-required parameter can specify a default value that is used if the parameter is not bound in a call.
7. A required tool parameter can specify a missing note based on present parameters to diagnose parameter omission.
8. A parameter type converts wire values to python values, providing feedback when conversion fails.
9. An identity parameter type provides a conversion that cannot fail when python and wire types are identical.
   - (woven with [8]): Identity conversion never produces conversion failure feedback.
10. A parameter type formed from other parameter types propagates all failures from constituent parameter types during conversion.
    - (woven with [8]): When converting a composite parameter type, failure of any constituent conversion propagates that constituent's failure feedback.
11. An agent can call tools by name with by-name wire parameter bindings via the tool manager.
12. For each call, the tool manager resolves symbols, converts, provides default values, and checks requirements, failing if a tool is not called properly.
    - (woven with assumption [1], [4]): When the tool name to call does not match any installed tool, the call fails with feedback indicating the unknown tool and listing installed tools.
    - (woven with [5, 7]): When a required parameter is omitted from the call and specifies a missing note, the call fails with feedback indicating the missing parameter and the missing note.
    - (woven with [5]): When a required parameter is omitted from the call and lacks a missing note, the call fails with feedback indicating the missing parameter.
    - (woven with [8]): When converting a wire parameter value fails, the call fails with feedback indicating the parameter conversion failure and the failure feedback.
    - (woven with [6]): When a non-required parameter is omitted from the call and specifies a default value, the default value is bound for the call.
    - (woven with [11, 13, 14]): When all parameter symbols and requirements are properly resolved, the tool is called with python type parameter bindings, returning its tool response.
13. A tool call leads to a tool response that provides tool output and informs the agent if the conversation should terminate.
14. A tool call fails when tool-specific execution conditions fail, indicated in the tool response with feedback on why the failure occurred.
15. A tool response can provide a suppression key to supersede and hide prior conversation responses associated with the same key.
16. When a tool call can reliably predict a subsequent tool call that the agent is likely to make, a tool response can designate a follow-up tool call specifying the next tool name, parameter values, and reasoning text.

## Grounding Facts

### Knowledge Needed

- Tool definitions and parameter specifications.
- Parameter type conversion rules.
- Wire parameter bindings.
- Tool response attributes.

### Actions Needed

- Install and enumerate tools in tool manager.
- Resolve parameter bindings and apply defaults.
- Convert wire values and validate required parameters.
- Execute tools with converted parameters.
- Construct tool response records.
