# sandbox_run_control interface component

imports: tool_provider, agent_file_alias, dag_storage, agent_node_config

## Purpose

The sandbox_run_control interface component provides explicit agent session outcome controls for successful task completion, upstream defect attribution, and failure termination.

Autonomous agents require unambiguous control tools to signal when a task is finished, when an irrecoverable error has occurred, or when prerequisites contain defects. Without structured termination tools, agents can loop indefinitely, silently drop errors, or conclude sessions without documenting their changes. The sandbox_run_control interface component establishes a governed termination boundary that verifies session criteria, enforces change documentation when files are modified, and routes diagnostic feedback to responsible dependency nodes.

**Out of scope:** The sandbox_run_control interface component does not execute build runners, format source files, inject startup tool calls, or manage filesystem state; these are handled by other components.

## Types and Behavior

The *run controller* is an agent session service configured with *blame targets*, which are bound files owned by upstream dependency nodes in dag storage, and verification checks. The run controller provides tools for terminating agent sessions and attributing outcomes.

The run controller:

- Exposes verification checks that validate session criteria.

- Caches verification evaluation results alongside the edit manager file update revision, reusing the cached verification outcome as long as no workspace files have been updated since that evaluation.

- Installs an *advance tool* when guide step mode is active, coordinating step progression through guide delivery upon passing verification.

- Installs a *finish tool* that concludes the session upon passing verification and enforces change documentation.

- Installs a *fail tool* that terminates the run in failure.

- Installs a *check file tool* that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.

- Installs a *blame tool* when blame targets are configured, attributing task failure to an upstream dependency node.
