<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-11T02:58:39Z
CHANGE: Align agent config typing with canonical policy properties and supersede arg keep resolution
CODE_HASH: 75adcfacf4d8
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# agent_config interface component

## Intent

Autonomous agent workflows require explicit bounds on conversational depth, automated tool chaining, instructional delivery modes, and session initialization. Without centralized agent operational policies, individual drivers and execution environments risk unbound execution loops, inconsistent instruction pacing, and uncoordinated file reads. The agent_config interface component establishes a unified system service that exposes conversational turn limits, follow-up injection policies, step mode guidance, and startup file read rules.

The component serves as a system-level configuration authority defining operational boundaries across agent runs.

## Factored Contracts

### Typing

- A conversation limit bounds the model interaction turns permitted in an agent run.
- A supersede arg keep limit bounds the trailing characters of a superseded string argument retained as a recognizable hint, resolving from the agent session configuration.
- A follow-up injection policy directs the agent to execute the follow-up tool calls that tool responses specify.
- A step mode policy permits the agent to receive a guide progressively.
- A startup read policy directs the agent to inspect declared files at session start.
- A delta output policy directs editing tools to report the changes they make rather than complete file content.

### Contracts

- A system's agent config exposes execution parameters for agent sessions. [expose_execution_parameters]

### Woven Contracts

- The agent config provides system-level execution parameters governing conversation turn limits, follow-up injection, step mode, startup reads, delta output, and supersede character preservation. [expose_execution_parameters]

## Grounding

### Knowledge Provisions

- Operational policy parameters bounding conversation depth and tool behaviors. [agent_configuration_parameters]

### Knowledge Requirements

- System-wide agent configuration parameters from environment or model configuration.
  - Deferred: Provided by system runtime configuration.
