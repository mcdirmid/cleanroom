# run_control

imports: tool_provider, virtual_file_name, dag_storage, dag_node_cleaner, change_summary_validator
types from tool_provider: tool, tool provider, tool result, tool failure, termination outcome
types from virtual_file_name: virtual file name
types from dag_storage: node
types from dag_node_cleaner: feedback message, change message
types from change_summary_validator: change validator, change summary

## Purpose

Enforces task verification, bounds change summaries, and routes blame feedback to upstream dependencies.

Agents frequently claim completion without testing changes or fail when upstream inputs are flawed. Run control gates termination on verification, requires concise change summaries for file edits, and provides a blame tool to route actionable feedback to responsible dependency nodes rather than failing the run.

## Types

- An *advance tool* is a *tool* that verifies session state, validates *change summaries*, and produces a *termination outcome* on success
- A *fail tool* is a *tool* that terminates an agent run in failure
- A *blame tool* is a *tool* that attributes incomplete tasks to dependency *nodes* and routes *feedback messages*
- A *blame target* is a source file addressed by a *virtual file name* owned by a dependency *node*
- A *run controller* is a *tool provider* providing an *advance tool*, a *fail tool*, and an optional *blame tool*
- A *run control factory* is a provider that constructs *run controllers* configured for specific sessions

## Behavior

- Creating a *run controller* through a *run control factory* yields a *run controller* configured with verification checks and *blame targets*.
- A *run controller* provides an *advance tool*, a *fail tool*, and a *blame tool* when *blame targets* are configured.
- A *run controller* validates *change summaries* using a *change validator* when workspace file modifications occurred.
- Executing an *advance tool* verifies session state; advancing without modifying workspace files and without passing verification checks produces a *tool failure* with feedback and prevents termination.
- Executing an *advance tool* when workspace file modifications occurred and verification passes produces a *termination outcome* carrying a *change message*.
- Executing an *advance tool* when no workspace file modifications occurred and verification passes produces a *termination outcome* without a *change message*.
- Executing a *fail tool* produces a *termination outcome* communicating that the run failed.
- Executing a *blame tool* with valid *blame targets* produces a *termination outcome* carrying *feedback messages* addressed to the owning dependency *nodes*.
- Executing a *blame tool* with an invalid target produces a *tool failure* listing valid *blame targets*.
