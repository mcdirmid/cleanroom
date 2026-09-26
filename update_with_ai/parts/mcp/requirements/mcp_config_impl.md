# mcp_config_impl implementation component

imports: agent_config, dag_config
implements: agent_config, dag_config

## Assumptions and Requirements

### Requirements

1. The agent config provides the conversation limit bounding interaction turns.
2. The agent config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.
3. The agent config provides whether the agent should use step mode to communicate a guide progressively.
4. The agent config provides whether the agent should perform startup reads to inspect declared files at session start.
5. The agent config provides whether editing tools should produce delta output.
6. The agent config provides whether the agent should operate in mcp mode.
7. The dag config provides the node visit limit bounding node visits during graph cleaning.
8. The dag config provides the batch size bounding dirty nodes processed together in an agent session.

## Grounding Facts

### Knowledge Needed

- Conversation limit.
- Inject followups flag.
- Step mode flag.
- Startup reads flag.
- Delta output flag.
- MCP mode flag.
- Node visit limit.
- Batch size limit.

### Actions Needed

- Resolve configuration parameters from execution environment.
