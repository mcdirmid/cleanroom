<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:30:00Z
CHANGE: Define submission interface component
CODE_HASH: 3ce37c03c730
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# submission interface component

imports: tool_provider, file_alias

## Purpose

The submission interface component provides explicit agent session outcome tools for successful task completion, upstream defect attribution, and failure termination.

Autonomous agents require unambiguous control tools to signal when a task is finished, when an irrecoverable error has occurred, or when prerequisites contain defects. Without structured termination tools, agents can loop indefinitely, silently drop errors, or conclude sessions without documenting their changes. The submission interface component establishes a governed termination boundary that verifies session criteria, enforces change documentation when files are modified, and routes diagnostic feedback to responsible dependency nodes.

**Out of scope:** The submission interface component does not execute build runners, format source files, inject startup tool calls, or manage filesystem state; these are handled by other components.

**Delegated:** Tool installation and parameter conversion are delegated to tool_provider; file alias addressing is delegated to file_alias.

## Types and Behavior

A polymorphic *resolve tool* defines a file alias *resolve target* parameter identifying the active node being resolved. A resolve tool produces a terminating response when all active nodes are resolved, or a non-terminating response when other active nodes remain.

The *submit tool* is a resolve tool that concludes active nodes upon passing verification, resolves submitted target arguments supplied as canonical target strings or workspace-relative file paths against declared role targets, marks the resolve target clean in the current get work turn, and enforces change documentation. The submit tool accepts a text *change summary* parameter.

The *fail tool* is a resolve tool that terminates the run in failure. The fail tool accepts a text *explanation* parameter.

The *blame tool* is a resolve tool that attributes task failure to an upstream dependency node. The blame tool accepts a file alias *blame target* parameter and a text explanation parameter.
