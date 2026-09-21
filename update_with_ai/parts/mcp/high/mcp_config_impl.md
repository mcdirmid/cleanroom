# mcp_config_impl implementation component

implements: agent_config, dag_config

## Purpose

The mcp_config_impl implementation component realizes agent and DAG execution configuration parameters for Model Context Protocol server environments.

Coordinating autonomous sub-agents across external JSON-RPC boundaries requires dedicated operational parameters distinct from headless turn loops. In MCP execution, agents drive their own reasoning turns, file inspection is performed on demand rather than via automated startup reads, and file guard tools require explicit MCP mode enablement. The mcp_config_impl implementation component establishes a system configuration service that exposes MCP-appropriate execution limits, batch bounds, and tool operational modes.

**Out of scope:** The mcp_config_impl implementation component does not parse build manifests, manage active sub-agent sessions, or validate file paths; these are handled by other components.

## Types and Behavior

The mcp config operates as a system service providing execution parameters for agent sessions and dependency graph execution.

The mcp config resolves configuration settings from environment variables or standard defaults:

- The conversation limit resolves from the `CONVERSATION_LIMIT` or `MODEL_CONVERSATION_LIMIT` environment variable, defaulting to 50.

- Whether the agent should inject followups to execute follow-up tool calls specified by tool responses resolves from the `INJECT_FOLLOWUPS` environment variable, defaulting to false.

- Whether the agent should use step mode to communicate a guide progressively resolves from the `STEP_MODE` or `CLEANROOM_STEP_MODE` environment variable, defaulting to false.

- Whether the agent should perform startup reads to inspect declared files at session start resolves from the `STARTUP_READS` environment variable, defaulting to false.

- Whether editing tools should produce delta output resolves from the `EDIT_DELTA_OUTPUT` environment variable, defaulting to false.

- Whether the agent should operate in mcp mode resolves from the `MCP_MODE` or `CLEANROOM_MCP_MODE` environment variable, defaulting to true.

- The node visit limit bounding node visits during graph cleaning resolves from the `NODE_VISIT_LIMIT` environment variable, defaulting to 500.

- The batch size bounding dirty nodes processed together in an agent session resolves from the `BATCH_SIZE` environment variable, defaulting to 1.
