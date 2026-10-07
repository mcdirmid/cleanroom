<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: d6eb433c0032
-->

# agent_config interface component

## Intent

Autonomous agent workflows require explicit bounds on conversational depth, automated tool chaining, instructional delivery modes, and session initialization. Without centralized agent operational policies, individual drivers and execution environments risk unbound execution loops, inconsistent instruction pacing, and uncoordinated file reads. The agent_config interface component establishes a unified system service that exposes conversational turn limits, follow-up injection policies, step-by-step guidance modes, and startup file read rules.

The component serves as a system-level configuration authority defining operational boundaries across agent runs.

## Factored Contracts

### Typing

- An agent config specifies a conversation limit bounding model interaction turns.
- An agent config specifies a supersede argument keep limit bounding preserved trailing characters.
- An agent config indicates whether the agent injects followups for tool calls.
- An agent config indicates whether the agent can use step mode.
- An agent config indicates whether the agent performs startup reads.
- An agent config indicates whether the agent expects editing tools to produce delta output.

### Contracts

- A system's agent config exposes execution parameters for agent sessions. [expose_execution_parameters]

### Woven Contracts

- The agent config provides system-level execution parameters governing conversation turn limits, follow-up injection, step mode delivery, startup reads, delta editing outputs, and supersede character preservation. [expose_execution_parameters]

## Grounding

### Knowledge Provisions

- Operational policy parameters bounding conversation depth and tool behaviors. [agent_configuration_parameters]

### Knowledge Requirements

- System-wide agent configuration parameters from environment or model configuration.
  - Deferred: Provided by system runtime configuration.
