<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Replace the fragment policy lead-in with declarative policy properties and canonicalize policy terminology
CODE_HASH: 247b6a2a335e
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# agent_config interface component

## Purpose

The agent_config interface component defines execution limits, interaction modes, and read policies governing agent sessions.

Autonomous agent workflows require explicit bounds on conversational depth, automated tool chaining, instructional delivery modes, and session initialization. Without centralized agent operational policies, individual drivers and execution environments risk unbound execution loops, inconsistent instruction pacing, and uncoordinated file reads. The agent_config interface component establishes a unified system service that exposes conversational turn limits, follow-up injection policies, step-by-step guidance modes, and startup file read rules.

**Out of scope:** The agent_config interface component does not manage API credentials, parse build manifests, or compute graph schedules; these are handled by other components.

## Types and Behavior

A system's *agent config* provides execution parameters for agent sessions.

A *conversation limit* bounds the number of model interaction turns permitted in an agent run. A *supersede arg keep* limit bounds the number of trailing characters of a superseded string argument retained as a recognizable hint, resolving from agent session configuration.

An agent config also provides operational policies governing how the agent behaves during an agent run.

The policies of an agent config are:

- A *follow-up injection* policy directing the agent to execute the follow-up tool calls that tool responses specify.

- A *step mode* policy permitting the agent to receive a guide progressively.

- A *startup read* policy directing the agent to inspect declared files at session start.

- A *delta output* policy directing editing tools to report the changes they make rather than complete file content.
