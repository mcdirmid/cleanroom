<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:03Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Declare the run controller tier and split the multi-concern tool bullets into focused statements
CODE_HASH: 3934154abd03
SPEC_QA_AUDIT: 2026-10-11T22:09:03Z
-->

# sandbox_run_control interface component

imports: tool_provider, agent_file_alias, dag_storage, agent_node_config, dag_config

## Purpose

The sandbox_run_control interface component provides explicit agent session outcome controls for successful task completion, upstream defect attribution, and failure termination.

Autonomous agents require unambiguous control tools to signal when a task is finished, when an irrecoverable error has occurred, or when prerequisites contain defects. Without structured termination tools, agents can loop indefinitely, silently drop errors, or conclude sessions without documenting their changes. The sandbox_run_control interface component establishes a governed termination boundary that verifies session criteria, enforces change documentation when files are modified, and routes diagnostic feedback to responsible dependency nodes.

**Out of scope:** The sandbox_run_control interface component does not execute build runners, format source files, inject startup tool calls, or manage filesystem state; these are handled by other components.

**Delegated:** Tool installation and parameter conversion are delegated to tool_provider; file alias addressing is delegated to agent_file_alias; verification checks and blame targets are delegated to agent_node_config; the nodes being resolved are addressed through dag_storage.

## Types and Behavior

A polymorphic *resolve tool* defines a file alias *resolve target* parameter identifying the active node being resolved. A resolve tool produces a terminating response when all active nodes are resolved, or a non-terminating response when other active nodes remain.

An agent session's *run controller* is configured with per-node blame targets and node config verification checks, initializes session tools upon agent session entry, and provides tools for terminating agent sessions and attributing outcomes.

The run controller installs the submit tool, the fail tool, the check files tool, the get work tool, and the blame tool unconditionally, and installs the advance tool when guide step mode is active.

The run controller exposes the verification checks that validate session criteria, and caches verification evaluation results alongside the edit manager file hashes of target nodes, reusing a cached verification outcome while no workspace file has been updated since that evaluation.

The run controller installs an argument-free *check files tool* named `check_files`. Executing the check files tool updates outdated verification results, evaluates verification checks across all open targets and modified workspace files, presents aggregated verification outcomes to the agent, tracks the last tested file hashes, and fails when verification failed.

The run controller installs an *advance tool* when guide step mode is active. Executing the advance tool coordinates step progression through guide delivery upon passing verification.

The run controller installs a *submit tool* which is a resolve tool that concludes active nodes upon passing verification, marks the resolve target clean in the current get work turn, and enforces change documentation. The submit tool accepts a text *change summary* parameter.

The run controller installs a *fail tool* which is a resolve tool that terminates the run in failure. The fail tool accepts a text *explanation* parameter.

The run controller installs a *blame tool* which is a resolve tool that attributes task failure to an upstream dependency node. The blame tool accepts a file alias *blame target* parameter and a text explanation parameter.

The run controller installs a *get work tool* that retrieves active dirty nodes, materializes startup templates, and delivers the session task prompt. The get work tool accepts an integer *max batch size* parameter and specifies a follow-up execution of the advance tool when guide step mode is active.
