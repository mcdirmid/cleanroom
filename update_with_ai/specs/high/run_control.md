# run_control

imports: tool_provider (tool results, signals), dag_clean_logic (change message, feedback message, termination-result types), dag_storage (node message), agent_loop (run), file_view (virtual name)
terms (from tool_provider): tool failure
terms (from dag_clean_logic): feedback message
terms (from agent_loop): run
terms (from file_view): virtual name
terms (owned): blame, blame target, soft length bound, hard length bound

## Purpose

Provides verification and termination for a file-modifying agent session: verifying run state, bounding change summaries, and signaling successful or failing termination through the advance, failure, and blame operations. Enforces the feedback rule when a feedback message is pending.

## Terms

- Blame: a termination outcome that attributes the task's incompleteness to one or more dependencies and provides feedback on how to correct their outputs; blame is not failure.
- Blame target: an artifact the agent may blame — a dependency's declared source file, addressed by its virtual name.
- Soft length bound: the preferred maximum length of a change summary; a summary exceeding it is rejected with shortening guidance up to a grace count, then accepted when within the hard length bound.
- Hard length bound: the maximum length a change summary may reach; a summary exceeding it is rejected with hard-bound guidance up to a grace count, and a summary still exceeding it after the grace count turns success into failure.

## Contract

**Inputs**

- Configured: an optional verification callback; whether the run's pending messages include a feedback message; the blame targets (a mapping from each blameable artifact's virtual name to the node that owns it; may be empty); the diff size limit (the maximum characters a verification diff may report).
- Per call: a tool call (tool name and arguments, per tool_provider).

**Operations**

- Verify the run.
- Check a change summary.
- Blame.
- Fail.
- Complete the run.

**Guarantees**

- Verification runs as part of the advance operation; verification passes when no verification callback is configured, and is delegated to the callback when one is configured.
- When verification fails, the session continues with feedback; advance never terminates on a failing verification.
- Verification may maintain the node's lib/test BUILD file through the configured build linter; the BUILD file is not among the workspace's files, and such writes are not run writes and are not reported in change summaries.
- Termination tools: advance, failure, and blame. Advance signals successful termination; a valid blame signals successful termination; the failure operation ends the session in failure.
- Each (target, feedback) pair of a blame is delivered as a feedback message to the blamed artifact's owning node.
- Termination is at the agent's judgment: the agent signals termination when it considers its task complete, or when it cannot be completed.
- Advance signals successful termination when verification passes; when files were modified, it requires a change summary naming what changed in each file, directing the next reader's attention to the changes.
- When files were modified and the change summary is missing, malformed, or incomplete, advance signals a tool failure.
- Change summaries are bounded; a summary exceeding the bound is rejected with guidance; persistent rejection fails the run.
- When the run's pending messages include a feedback message, advance that would otherwise signal successful termination without a change signals a tool failure with a reason directing the agent to change, blame, or fail; the session continues.

**Assumptions**

- The verification callback, if provided, has no side effects on the workspace; it may only modify the node's lib/test BUILD file (maintained by the build linter), which is not among the workspace's files.
- The consumer routes termination signals and stubs the earlier result when a result's flag is set, identifying it by the verification command.

## Non-concerns

- Advance tool description: the advance tool's description wording is unspecified; the tool's contract is defined by the verification, termination, and step-mode rules.
- Bound values: the soft and hard length bound values and the grace count are unspecified here; they are pinned in the implementation spec.
