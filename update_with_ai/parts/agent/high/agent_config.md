# agent_config interface component

## Purpose

The agent_config interface component defines execution limits, interaction modes, and inspection policies governing agent sessions.

Autonomous agent workflows require explicit bounds on conversational depth, automated tool chaining, instructional delivery modes, and session initialization. Without centralized agent operational policies, individual drivers and execution environments risk unbound execution loops, inconsistent instruction pacing, and uncoordinated file inspections. The agent_config interface component establishes a unified system service that exposes conversational turn limits, follow-up injection policies, step-by-step guidance modes, and startup file inspection rules.

**Out of scope:** The agent_config interface component does not manage API credentials, parse build manifests, or compute graph schedules; these are handled by other components.

## Types and Behavior

A *conversation limit* is a bound on the maximum number of model interaction turns permitted in an agent run.

The *agent config* is a system service that provides execution parameters for agent sessions.

The agent config provides:

- The conversation limit bounding interaction turns.

- Whether the agent should *inject followups* to execute follow-up tool calls specified by tool responses.

- Whether the agent should use *step mode* to communicate a guide to the agent progressively.

- Whether the agent should perform *startup reads* to inspect declared files at session start.

- Whether editing tools should execute a *follow-up read* on modified files.

- Whether editing tools should produce *delta output*.
