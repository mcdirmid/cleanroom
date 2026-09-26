# agent_config interface component

## Assumptions and Requirements

### Requirements

1. The agent config provides the conversation limit bounding the maximum number of model interaction turns permitted in an agent run.
2. The agent config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.
3. The agent config provides whether the agent can use step mode to communicate a guide to the agent progressively.
4. The agent config provides whether the agent should perform startup reads to read declared files at session start.
5. The agent config provides whether editing tools should produce delta output.
6. The agent config provides whether the agent should operate in mcp mode.
7. The agent config provides the character retention limit bounding preserved string argument tails when tool responses are superseded.

## Grounding Facts

### Knowledge Needed

- Conversation limit.
- Inject followups flag.
- Step mode flag.
- Startup reads flag.
- Delta output flag.
- MCP mode flag.
- Character retention limit for superseded tool responses.

### Actions Needed

- Provide agent configuration parameters.
