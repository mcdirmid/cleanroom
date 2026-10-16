<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:30:00Z
CHANGE: Define sandbox_submission_impl realization
CODE_HASH: 29e567c84d8e
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# sandbox_submission_impl implementation component

imports: tool_provider, agent_file_alias, agent_node_config, sandbox_guide_delivery, src_metadata, control_coordinate, sandbox_run_control
implements: sandbox_submission

## Purpose

The sandbox_submission_impl implementation component realizes self-contained outcome resolution for submit, fail, and blame tools.

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The sandbox_submission_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and validates blame targets, converting outcome decisions into structured tool responses.

**Out of scope:** The sandbox_submission_impl implementation component does not execute build runners or manage execution loops; these are handled by other components.

**Delegated:** Tool parameter management is delegated to tool_provider; file alias addressing is delegated to agent_file_alias; guide step status is delegated to sandbox_guide_delivery; session configuration is delegated to agent_node_config; workspace modification status is delegated to src_metadata; session coordination and submission dispatch are delegated to control_coordinate; verification checks and run controllers are delegated to sandbox_run_control.

## Types and Behavior

A resolve tool defines a file alias resolve target parameter, accepting the short name target as an alias. A resolve tool matches the resolve target parameter against open active nodes by declared source file alias when the node declares one, by short unit name when that name is unique among active nodes, or by package-qualified unit name formatted as `pkg/unit_name` when the short name is ambiguous.

When the resolve target parameter is omitted, it defaults to:

- The single remaining unsubmitted open active node when only one node is being processed.

- The last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open active node.

A resolve tool:

- Fails when the resolve target parameter is omitted and cannot be defaulted, or when the specified resolve target parameter does not match an open active node, reminding the agent to specify an open target.

- Fails when an in-batch dependency of the resolve target is not clean in the current get work turn, reminding the agent that in-batch dependencies must be submitted before dependent targets.

- Marks in-batch dependent nodes as failed upon node failure or blame attribution.

- Produces a non-terminating response with a reminder listing the remaining active nodes formatted through the template formatter when other active nodes remain.

- Produces a terminating response when all active nodes are resolved, indicating successful session completion for submitted nodes, carrying the explanation for failed nodes, or attributing defect feedback to the owning node of the blame target for blamed nodes.

The submit tool is named `submit`, accepts a resolve target parameter and a text change summary parameter, and shares the constant suppression key `submit`. Executing the submit tool updates outdated verification results.

The submit tool:

- Fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call with reasoning text indicating that remaining guide steps must be completed before finishing.

- Fails when verification is failing, reminding the agent to call the check files tool first and specifying a follow-up execution of the check files tool with reasoning text indicating that verification results must be inspected before submitting.

- Dispatches target submission with the resolve target, change summary, and workspace modification status to the session coordinator. When submission fails due to unaddressed session feedback without workspace file modifications, produces a failure response reminding the agent that workspace files must be modified to address feedback before submitting or that fail must be called. Produces change summary reminders strictly when change summary documentation rules are violated.

- Produces a terminating response when submission succeeds and all active nodes are resolved, or a non-terminating response when open active nodes remain.

The fail tool is named `fail`, accepts a resolve target parameter and a text explanation parameter, and marks the active node as failed while resolving that active node.

The blame tool is named `blame`, accepts a resolve target parameter, a file alias blame target parameter, and a text explanation parameter. Active nodes never share feedback targets, so the blame tool identifies the active node attributing blame from the specified blame target.

The blame tool:

- Resolves the active node attributing blame from the specified blame target, or from the resolve target parameter when it matches a configured blame target.

- Defaults the blame target parameter to the single configured blame target of the remaining active node when omitted in a single-target context.

- Defaults the resolve target parameter using resolve target defaulting rules when the resolve target parameter is omitted and cannot be inferred from the blame target.

- Fails when the blame target does not match a configured blame target, providing an error response that lists the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.

- Fails when the explanation contains newline characters, providing an error response and reminding the agent that a blame explanation must be a single paragraph without newlines.

- Records defect feedback for the blamed target in graph storage, marks the blame target as attributed, and resolves the active node.
