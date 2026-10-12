<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-12T11:59:00Z
CHANGE: Install advance tool and specify follow-up execution when guide step mode is active in get work tool
CODE_HASH: c34cea1a7708
SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
-->

# sandbox_run_control_impl implementation component

imports: tool_provider, agent_file_alias, dag_storage, sandbox_file_editor, sandbox_guide_delivery, agent_node_config, template_format, dag_subgraph, sandbox, control_coordinate
implements: sandbox_run_control

## Purpose

The sandbox_run_control_impl implementation component realizes self-contained outcome evaluation, guide step mode advancement, and verification checks for advance, submit, fail, blame, check files, and get work tools.

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The sandbox_run_control_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and validates blame targets, converting outcome decisions into structured tool responses.

**Out of scope:** The sandbox_run_control_impl implementation component does not parse syntax trees or compute topological dependency schedules; these are handled by other components.

**Delegated:** File storage, template materialization, and metadata mutation concerns are delegated to dag_storage; session coordination, verification evaluation, work discovery, submission gating, and outcome attribution are delegated to control_coordinate.

## Types and Behavior

The run controller initializes session tools on agent session entry, obtaining verification checks and per-node blame targets from node config, and delegating active target tracking, verification evaluation, submission gating, defect attribution, and work discovery to the session coordinator.

The run controller evaluates verification checks for an active node sequentially against the latest content of the active read-write file, and caches the outcome alongside that file's edit manager hash. Cached verification results are reused while the file hash is unchanged, so repeated verification requests avoid redundant evaluation.

The check files tool is named `check_files`, accepts no parameters, and shares the constant suppression key `check_files`. Executing the check files tool updates outdated verification results and evaluates verification checks across all open targets and modified workspace files.

The check files tool:

- Reminds the agent that verification passed or failed, and that no new information will be revealed by the tool call until session read-write files are updated, when target read-write file hashes are unchanged since the previous check files tool execution.

- Fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.

- Produces a response presenting passing verification results using the session verification success message when configured, or default passing verification results alongside sanitized check output when verification passes.

The advance tool is named `advance`, accepts no parameters, and shares the constant suppression key `advance`.

The advance tool:

- Fails when verification has not been evaluated for the current workspace files or is failing, repeating the primer and summary content alongside failure diagnostics through guide delivery on the first step, reminding the agent to call the check files tool first, and specifying a follow-up execution of the check files tool with reasoning text indicating that verification results must be inspected before advancing.

- Advances guide delivery and delivers the next step section when verification is passing and guide steps remain.

- Fails with a reminder to call the submit tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.

- Produces a response specifying a follow-up execution of the submit tool without a change summary and with reasoning text indicating that all guide steps are complete when verification is passing, no steps remain, and no workspace files were modified.

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

- Fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.

- Fails when a change summary is provided while resolving an auditor node, reminding the agent that change summaries are not permitted for audit nodes.

- Fails when workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing a session after modifying workspace files.

- Fails when workspace files were not modified and a change summary is provided, reminding the agent that change summaries are not permitted when submitting without workspace file modifications.

- Marks the resolve target clean in graph storage with the provided change summary, marks the resolve target clean and submitted in the current get work turn, and resolves the active node.

The fail tool is named `fail`, accepts a resolve target parameter and a text explanation parameter, and marks the active node as failed while resolving that active node.

The blame tool is named `blame`, accepts a resolve target parameter, a file alias blame target parameter, and a text explanation parameter. Active nodes never share feedback targets, so the blame tool identifies the active node attributing blame from the specified blame target.

The blame tool:

- Resolves the active node attributing blame from the specified blame target, or from the resolve target parameter when it matches a configured blame target.

- Defaults the blame target parameter to the single configured blame target of the remaining active node when omitted in a single-target context.

- Defaults the resolve target parameter using resolve target defaulting rules when the resolve target parameter is omitted and cannot be inferred from the blame target.

- Fails when the blame target does not match a configured blame target, providing an error response that lists the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.

- Fails when the explanation contains newline characters, providing an error response and reminding the agent that a blame explanation must be a single paragraph without newlines.

- Records defect feedback for the blamed target in graph storage, marks the blame target as attributed, and resolves the active node.

The get work tool is named `get_work`.

The get work tool:

- Fails when open active nodes remain, reminding the agent that open nodes must be resolved before requesting new work.

- Obtains dirty nodes from dag storage and dag subgraph when no open active nodes remain, updating the active nodes and the execution version on role config.

- Produces an idle response indicating that no dirty nodes are ready when no dirty node is ready for cleaning.

The get work tool materializes startup templates through graph storage, initializes guide delivery, and returns the rendered task primer when ready dirty nodes are obtained and guide step mode is inactive. That task primer maps each node to its grounding file with guide file attribution, incoming messages, alignment instructions, and target resolution instructions, identifying each node by declared source file alias, by short unit name when unique among batch nodes, or by package-qualified unit name when ambiguous. Target resolution instructions specify target as a short unit name when unique or as a package-qualified unit name when ambiguous in multi-node batches, and indicate that target may be omitted when only one node is being processed.

The get work tool materializes startup templates through graph storage, initializes guide delivery, installs the advance tool into the tool manager, records the task primer in guide delivery, and returns the task primer when ready dirty nodes are obtained and guide step mode is active. That task primer maps source files to grounding files, guide summary, incoming messages, and instructions to call the advance tool once edits are complete, without guide file citation and specifying a follow-up execution of the advance tool.
