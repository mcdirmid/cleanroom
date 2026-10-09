<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 4f1672fa2e1c
-->

# control_attribution interface component

imports: agent_session, dag_storage, agent_file_alias, agent_node_config, src_metadata

## Purpose

The control_attribution interface component defines defect feedback routing, upstream blame validation, and failure outcome recording for failed targets.

When an implementation cannot be completed due to missing contracts, contradictory specifications, or defective upstream artifacts, agents must attribute failures accurately rather than attempting invalid workarounds or failing silently. Without structured blame attribution, upstream defects remain undetected, leading to repetitive downstream failures. The control_attribution interface component validates that blamed culprits are declared upstream dependencies, enforces single-paragraph critique formatting, injects feedback messages into graph storage, marks culprits dirty for rework, and records explicit failure diagnostics.

**Out of scope:** The control_attribution interface component does not modify source code files or trigger automatic retries; these are handled by other components.

**Delegated:** Feedback message storage and node status mutations are delegated to dag_storage; in-band source metadata extraction and feedback formatting are delegated to src_metadata.

## Types and Behavior

An *attribution outcome* records the result of an attribution or failure action, reporting whether the action was *accepted*, carrying an outcome *message*, and identifying any *affected nodes*.

A session's *attribution coordinator* manages blame attribution and failure recording.

The attribution coordinator:

- Validates that a blamed culprit is an upstream dependency of the source target node configured to receive feedback.

- Enforces that blame explanations consist of a single continuous paragraph without newline characters or line breaks.

- Attributes blame by recording a feedback message on the culprit node in graph storage, marking the culprit node status as dirty, and marking in-batch dependent nodes as failed.

- Records task failure for a target node by logging the failure explanation, preserving dirty status on the target node, and marking dependent nodes as failed.

- Attributes defect blame to culprit files in repository workspaces by validating that critique explanations contain no newline characters, invoking build blame targets or appending in-band feedback messages and dirty markers directly to culprit files in canonical repositories, and synchronizing updated files back to local role workspaces.

- Records task failure for file targets by appending failure diagnostics and marking dirty status in canonical repositories, synchronizing updated files back to local role workspaces.
