# attribution interface component

imports: session, dag_storage, file_alias, node_config, src_metadata

## Purpose

The attribution interface component defines defect feedback routing, upstream blame validation, and failure outcome recording for failed targets.

When an implementation cannot be completed due to missing contracts, contradictory specifications, or defective upstream artifacts, agents must attribute failures accurately rather than attempting invalid workarounds or failing silently. Without structured blame attribution, upstream defects remain undetected, leading to repetitive downstream failures. The attribution interface component validates that blamed culprits are declared upstream dependencies, enforces single-paragraph critique formatting, injects feedback messages into graph storage, marks culprits dirty for rework, and records explicit failure diagnostics.

**Out of scope:** The attribution interface component does not modify source code files or trigger automatic retries; these are handled by other components.

**Delegated:** Feedback message storage and node status mutations are delegated to dag_storage; in-band source metadata extraction and feedback formatting are delegated to src_metadata; file alias addressing is delegated to agent_file_alias; session lifecycle scoping is delegated to agent_session.

## Types and Behavior

An *attribution outcome* records the result of an attribution or failure action, reporting whether the action was *accepted*, carrying an outcome *message*, and identifying any *affected nodes*.

An agent session's *attribution coordinator* manages blame attribution and failure recording.

The attribution coordinator validates that a blamed culprit is an upstream dependency of the source target node configured to receive feedback, resolves blame targets via alias resolution, exact path match, or normalized relative path suffix matching, and enforces that blame explanations consist of a single continuous paragraph, sanitizing multi-line explanations by collapsing line breaks into spaces and validating that the critique does not exceed configured maximum feedback character limits (defaulting to 2000 characters when unconfigured) and advising prioritization when exceeded.

The attribution coordinator attributes blame by recording a feedback message on the culprit node in graph storage, marking the culprit node status as dirty, and marking in-batch dependent nodes as failed. The attribution coordinator records task failure for a target node by logging the failure explanation, preserving dirty status on the target node, and marking dependent nodes as failed.

The attribution coordinator attributes defect blame to a culprit file in a repository workspace by sanitizing the critique explanation to collapse multi-line breaks into a single continuous paragraph without exceeding configured maximum feedback character limits (defaulting to 2000 characters when unconfigured), resolving the culprit file via alias resolution, exact path matching, or normalized relative path suffix matching against registered blame targets, discovering role context from workspace metadata or execution environment, then invoking a build blame target or appending in-band feedback and dirty markers directly to the culprit file in the canonical repository and synchronizing the updated file back to the local role workspace.

The attribution coordinator records task failure for a file target by discovering role context from workspace metadata or execution environment: for authoring roles, appending failure diagnostics and marking dirty status in the canonical repository and synchronizing the updated file back to the local role workspace; for auditor roles, recording task failure strictly within the auditor workspace without mutating or appending feedback to the audited file in the canonical repository.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T11:00:00Z
LAST_CHANGED: 2026-10-30T11:00:00Z
CHANGE: Sanitize multi-line blame critiques by collapsing line breaks into continuous paragraph
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
