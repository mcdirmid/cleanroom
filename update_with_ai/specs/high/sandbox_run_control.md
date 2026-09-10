# sandbox_run_control interface component

imports: tool_provider, file_alias, dag_storage

## Purpose

The sandbox_run_control interface component provides explicit agent session outcome controls for successful task completion, upstream defect attribution, and failure termination.

Autonomous agents require unambiguous control tools to signal when a task is finished, when an irrecoverable error has occurred, or when prerequisites contain defects. Without structured termination tools, agents can loop indefinitely, silently drop errors, or conclude sessions without documenting their changes. The sandbox_run_control interface component establishes a governed termination boundary that verifies session criteria, enforces change documentation when files are modified, and routes diagnostic feedback to responsible dependency nodes.

**Out of scope:** The sandbox_run_control interface component does not execute build runners, format source files, inject startup tool calls, or manage filesystem state; these are handled by other components.

## Types and Behavior

A *verification check* is a polymorphic service that validates session criteria, communicating whether verification passed and diagnostic feedback on failure.

The *run controller* is an agent session service configured with *blame targets*, which are bound files owned by upstream dependency nodes in dag storage, and verification checks. The run controller installs tools for terminating agent sessions and attributing outcomes. The run controller:

- Exposes verification checks that validate session criteria during advancement.

- Installs an *advance tool* that coordinates session progression and completion.

- Installs a *fail tool* that terminates the run in failure.

- Installs a *blame tool* that attributes task failure to an upstream dependency node. The run controller installs the blame tool when blame targets are configured. Executing the blame tool fails if the target is not one of the blame targets, and terminates the run with diagnostic feedback attributed to the owning node on success.
