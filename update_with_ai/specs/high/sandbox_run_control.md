# sandbox_run_control interface component

imports: tool_provider, file_alias, dag_storage, sandbox_file_editor, sandbox_guide_delivery

## Purpose

The sandbox_run_control interface component provides explicit agent session outcome controls for successful task completion, upstream defect attribution, and failure termination.

Autonomous agents require unambiguous control tools to signal when a task is finished, when an irrecoverable error has occurred, or when prerequisites contain defects. Without structured termination tools, agents can loop indefinitely, silently drop errors, or conclude sessions without documenting their changes. The sandbox_run_control interface component establishes a governed termination boundary that verifies session criteria, enforces change documentation when files are modified, and routes diagnostic feedback to responsible dependency nodes.

**Out of scope:** The sandbox_run_control interface component does not execute build runners, format source files, inject startup tool calls, or manage filesystem state; these are handled by other components.

## Types and Behavior

A *verification check* is a polymorphic service that validates session criteria, communicating whether verification passed and diagnostic feedback on failure.

The *run controller* is an agent session service configured with *blame targets*, which are bound files owned by upstream dependency nodes in dag storage. The run controller maintains verification checks and installs tools for terminating agent sessions and attributing outcomes. Verification checks can be *installed* on the run controller so they are evaluated during session advancement. The run controller installs:

- An *advance tool* that coordinates session progression and completion. When progressive guide delivery is configured and steps remain in guide delivery, executing the advance tool advances the guide step delivery and returns the next step content without terminating the run. A call to the advance tool can be injected when an agent session starts when using step mode to deliver initial step content. When all guide steps are completed or progressive guide delivery is not configured, executing the advance tool evaluates installed verification checks and completes the session, terminating the run, but fails if workspace file modifications occurred (as tracked by the edit manager) and no change summary was provided.

- A *fail tool* that terminates the run in failure.

- A *blame tool* that attributes task failure to an upstream dependency node. The run controller installs the blame tool when blame targets are configured. Executing the blame tool fails if the target is not one of the blame targets, and terminates the run with diagnostic feedback attributed to the owning node on success.
