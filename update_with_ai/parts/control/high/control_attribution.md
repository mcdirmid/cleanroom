<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-11T02:45:00Z
CHANGE: Name the session attribution coordinator and split the multi-concern file attribution bullets
CODE_HASH: 8351f2584a6f
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# control_attribution interface component

imports: agent_session, dag_storage, agent_file_alias, agent_node_config, src_metadata

## Purpose

The control_attribution interface component defines defect feedback routing, upstream blame validation, and failure outcome recording for failed targets.

When an implementation cannot be completed due to missing contracts, contradictory specifications, or defective upstream artifacts, agents must attribute failures accurately rather than attempting invalid workarounds or failing silently. Without structured blame attribution, upstream defects remain undetected, leading to repetitive downstream failures. The control_attribution interface component validates that blamed culprits are declared upstream dependencies, enforces single-paragraph critique formatting, injects feedback messages into graph storage, marks culprits dirty for rework, and records explicit failure diagnostics.

**Out of scope:** The control_attribution interface component does not modify source code files or trigger automatic retries; these are handled by other components.

**Delegated:** Feedback message storage and node status mutations are delegated to dag_storage; in-band source metadata extraction and feedback formatting are delegated to src_metadata; file alias addressing is delegated to agent_file_alias; session lifecycle scoping is delegated to agent_session.

## Types and Behavior

An *attribution outcome* records the result of an attribution or failure action, reporting whether the action was *accepted*, carrying an outcome *message*, and identifying any *affected nodes*.

An agent session's *attribution coordinator* manages blame attribution and failure recording.

The attribution coordinator validates that a blamed culprit is an upstream dependency of the source target node configured to receive feedback, and enforces that blame explanations consist of a single continuous paragraph without newline characters.

The attribution coordinator attributes blame by recording a feedback message on the culprit node in graph storage, marking the culprit node status as dirty, and marking in-batch dependent nodes as failed. The attribution coordinator records task failure for a target node by logging the failure explanation, preserving dirty status on the target node, and marking dependent nodes as failed.

The attribution coordinator attributes defect blame to a culprit file in a repository workspace by validating that the critique explanation contains no newline characters, then invoking a build blame target or appending in-band feedback and dirty markers directly to the culprit file in the canonical repository and synchronizing the updated file back to the local role workspace.

The attribution coordinator records task failure for a file target by appending failure diagnostics and marking dirty status in the canonical repository, then synchronizing the updated file back to the local role workspace.
