<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:30:00Z
CHANGE: Update run_control interface component
CODE_HASH: 9a9b755e4181
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# run_control interface component

imports: tool_provider, file_alias, dag_storage, node_config

## Purpose

The run_control interface component provides explicit agent session run execution controls, verification checking, milestone progression, and work acquisition.

Autonomous agents require unambiguous control tools to signal when a task is finished, when an irrecoverable error has occurred, or when prerequisites contain defects. Without structured termination tools, agents can loop indefinitely, silently drop errors, or conclude sessions without documenting their changes. The run_control interface component establishes a governed execution boundary that coordinates verification checks, advances step guidance, acquires active dirty work, and installs session outcome tools.

**Out of scope:** The run_control interface component does not execute build runners, format source files, inject startup tool calls, or manage filesystem state; these are handled by other components.

**Delegated:** Tool installation and parameter conversion are delegated to tool_provider; file alias addressing is delegated to agent_file_alias; verification checks and blame targets are delegated to agent_node_config; the nodes being resolved are addressed through dag_storage.

## Types and Behavior

An agent session's *run controller* is configured with per-node blame targets and node config verification checks, initializes session tools upon agent session entry, and provides tools for terminating agent sessions and attributing outcomes.

The run controller installs the submit tool, the fail tool, the check files tool, and the get work tool unconditionally, and installs the advance tool when guide step mode is active. The get work tool installs the blame tool when any active node has configured blame targets.

The run controller exposes the verification checks that validate session criteria, and caches verification evaluation results alongside the edit manager file hashes of target nodes, reusing a cached verification outcome while no workspace file has been updated since that evaluation.

The run controller installs an argument-free *check files tool* named `check_files`. Executing the check files tool updates outdated verification results, evaluates verification checks across all open targets and modified workspace files, presents aggregated verification outcomes to the agent, tracks the last tested file hashes, and fails when verification failed.

The run controller installs an *advance tool* when guide step mode is active. Executing the advance tool coordinates step progression through guide delivery upon passing verification.

The run controller installs an argument-free *get work tool* named `get_work` that retrieves active dirty nodes, materializes startup templates, delivers the session task prompt, resolves the primary guide file from provisioned read-only documentation when not explicitly declared on node configuration, and specifies a follow-up execution of the advance tool when guide step mode is active.
