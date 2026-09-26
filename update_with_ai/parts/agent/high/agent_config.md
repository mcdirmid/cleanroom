# agent_config interface component

## Purpose

The agent_config interface component defines execution limits, interaction modes, and read policies governing agent sessions.

Autonomous agent workflows require explicit bounds on conversational depth, automated tool chaining, instructional delivery modes, and session initialization. Without centralized agent operational policies, individual drivers and execution environments risk unbound execution loops, inconsistent instruction pacing, and uncoordinated file reads. The agent_config interface component establishes a unified system service that exposes conversational turn limits, follow-up injection policies, step-by-step guidance modes, and startup file read rules.

**Out of scope:** The agent_config interface component does not manage API credentials, parse build manifests, or compute graph schedules; these are handled by other components.

## Types and Behavior

A system's *agent config* provides execution parameters for agent sessions.

The agent config provides a conversation limit bounding the maximum number of model interaction turns permitted in an agent run. The agent config also provides a *supersede arg keep* limit bounding trailing characters of string arguments preserved when tool responses are superseded. The agent config also provides whether the agent:

- Injects followups to execute follow-up tool calls specified by tool responses.

- Can use step mode to communicate a guide to the agent progressively.

- Performs startup reads to read declared files at session start.

- Operates in mcp mode.

- Expects editing tools to produce delta output.


