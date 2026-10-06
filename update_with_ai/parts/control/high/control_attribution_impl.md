# control_attribution_impl implementation component

imports: agent_session, dag_storage, agent_file_alias, agent_node_config
implements: control_attribution

## Purpose

The control_attribution_impl implementation component realizes upstream culprit matching, single-paragraph validation, feedback message injection, and cascade failure propagation.

Accurate defect attribution requires verifying that blame is directed exclusively to declared upstream dependencies rather than unrelated components or downstream artifacts. The control_attribution_impl implementation component validates blame targets against configured dependency nodes, enforces concise single-paragraph critiques, routes feedback messages into graph storage for the upstream owner, marks the culprit dirty so it re-enters the work schedule, and automatically fails downstream in-batch dependent nodes.

**Out of scope:** The control_attribution_impl implementation component does not edit file comments or reorder git history; these are handled by other components.

**Delegated:** Feedback message storage and node status mutations are delegated to dag_storage.

## Types and Behavior

The attribution coordinator implements defect attribution and failure recording for the session.

When attributing blame to an upstream target:

- The attribution coordinator validates that the blame target corresponds to a declared upstream dependency of the source target configured to receive feedback. If the blame target is not an eligible dependency, attribution is rejected with an error listing available blame targets.

- The attribution coordinator validates that the explanation string contains no newline characters, rejecting explanations that contain multiple paragraphs or line breaks.

- The attribution coordinator checks that any in-batch dependencies of the source target are clean before attributing blame.

- Upon successful validation, the attribution coordinator creates a feedback message containing the explanation and records it on the culprit node in graph storage.

- The attribution coordinator marks the culprit node status as dirty in graph storage, marks the source target as attributed, and marks any in-batch dependent nodes as failed.

When recording task failure:

- The attribution coordinator records the failure explanation on the target node in graph storage.

- The attribution coordinator preserves the dirty status on the target node, marks the node as failed in the active session, and marks in-batch dependent nodes as failed.
