<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:30:00Z
CHANGE: Update run_control_impl realization component
CODE_HASH: a7ac878d4dd1
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# run_control_impl implementation component

imports: tool_provider, file_alias, dag_storage, file_editor, guide_delivery, node_config, template_format, subgraph, coordinate, submission
implements: run_control

## Purpose

The run_control_impl implementation component realizes self-contained execution loop control, guide step mode advancement, and verification checks for check files, advance, and get work tools.

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The run_control_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and manages session tool installation.

**Out of scope:** The run_control_impl implementation component does not parse syntax trees or compute topological dependency schedules; these are handled by other components.

**Delegated:** File storage, template materialization, and metadata mutation concerns are delegated to dag_storage; session coordination, verification evaluation, work discovery, submission gating, and outcome attribution are delegated to coordinate; outcome resolution tools are delegated to submission.

## Types and Behavior

The run controller initializes session tools on agent session entry, obtaining verification checks and per-node blame targets from node config, installing standard session tools (submit, fail, check files, and get work), and delegating active target tracking, verification evaluation, submission gating, defect attribution, and work discovery to the session coordinator.

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

The get work tool is named `get_work`.

The get work tool:

- Fails when open active nodes remain, reminding the agent that open nodes must be resolved before requesting new work.

- Obtains dirty nodes from dag storage and dag subgraph when no open active nodes remain, updating the active nodes and the execution version on role config.

- Produces an idle response indicating that no dirty nodes are ready when no dirty node is ready for cleaning.

When ready dirty nodes are obtained, the get work tool installs the blame tool into the tool manager if and only if any active node has configured blame targets in node config.

The get work tool materializes startup templates through graph storage, initializes guide delivery, and returns the rendered task primer when ready dirty nodes are obtained and guide step mode is inactive. That task primer maps each node to its grounding file with guide file attribution, incoming messages, alignment instructions, and target resolution instructions, identifying each node by declared source file alias, by short unit name when unique among batch nodes, or by package-qualified unit name when ambiguous. Target resolution instructions specify target as a short unit name when unique or as a package-qualified unit name when ambiguous in multi-node batches, and indicate that target may be omitted when only one node is being processed.

The get work tool materializes startup templates through graph storage, initializes guide delivery, installs the advance tool into the tool manager, records the task primer in guide delivery, and returns the task primer when ready dirty nodes are obtained and guide step mode is active. That task primer maps source files to grounding files, guide summary, incoming messages, and instructions to call the advance tool once edits are complete, without guide file citation and specifying a follow-up execution of the advance tool.
