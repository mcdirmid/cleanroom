<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - dag_clean_logic.md
  - dag_storage.md
  - file_view.md
  - guide_delivery.md
  - run_control.md
-->

# Implementation LLS: run_control_impl

## Data Types
```python
from run_control import RunControl, RunControlConfig, Blame
from file_view import FileView
from guide_delivery import GuideDelivery
from tool_provider import (
    TerminateAgentWithFailure,
    TerminateAgentWithSuccess,
    ToolFailure,
    T_tool,
)
from dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult
from dag_storage import NodeId, NodeMessage

class RunControlImpl(RunControl):
    def __init__(
        self,
        config: RunControlConfig,
        file_view: FileView,
        guide_delivery: GuideDelivery,
    ): ...
```

Constructed with the `run_control` interface's `RunControlConfig`, the `file_view` interface (for the changed-file and diff information the termination rules read) and the `guide_delivery` interface (for the step-state gating the advance rules consult). Implements the `RunControl` Protocol, providing all operations: `get_tool_definitions`, `advance`, `fail`, and `blame`.

## Behavioral Description

The implementation:
- Delegates verification to the injected verification callback when provided.
- `advance` performs the session's verification internally: it computes the diff of the session's changes (the changed files and their session-start snapshots, via the configured `file_view`), truncated when it exceeds the diff size limit (reporting the truncated size and the full change counts) and, when configured, runs the injected verification callback; on a failing verification it provides feedback (never a tool failure) and the session continues; a failing verification's feedback does not include the diff.
- `advance`'s step-mode gating follows guide_delivery's output rule: on a failing verification in step mode, the output is the restated guide summary with the reason (via `guide_delivery.get_advance_output`); on a passing verification with step sections remaining, the output is the next step section; on a passing verification with no step sections remaining, `advance` proceeds to the termination machinery.
- Change summaries are bounded by the soft length bound and the hard length bound: `advance` rejects a change message over the soft bound with shortening guidance up to a grace count, then accepts it when within the hard bound; a change message still over the hard bound after the grace count fails the session (`advance` turns into `TerminateAgentWithFailure`). The bound values are pinned in Non-Concerns.
- A missing or out-of-bounds change message signals a `ToolFailure` that lists the changed files and shows the session's diff.
- The feedback-pending gate is checked only when advance would otherwise signal successful termination without a change; a failing verification and the change-message requirement are checked first.
- Sets the supersession flag on verification results, never on termination results.
- `blame` resolves each `Blame` pair's target (a blameable artifact's virtual name) through the configured `blame_targets` mapping to the owning node's `NodeId` before forming the feedback result; each pair is one (target, feedback) feedback message — a `NodeMessage` with kind `feedback` and text the feedback — delivered to the owning node.
- `blame` with no configured blame targets returns `ToolFailure[str]` (a precondition violation; the tool is not offered when targets are empty).
- Forms the `TerminateAgentWithSuccess` result using `dag_clean_logic` result types:
  - `advance` — carries `NoChangeResult()` when no file's current content differs from its session-start snapshot (writes may have occurred but net out to no change), or `ChangeResult` with messages built from `changes` when files changed; rejects a change summary for a net-unchanged file (its content equals its session-start snapshot), and directs a session whose writes all net out to report no change (advance with no changes)
  - `blame` (valid pairs) — carries `FeedbackResult` whose messages convert each resolved `(target, feedback)` pair into a `(NodeId, NodeMessage)` pair — the target as the `NodeId`, the feedback as a `NodeMessage` with kind `feedback` and text the feedback
- `fail` returns `TerminateAgentWithFailure[str]` with its value pinned to `Task failed` (tests may assert it).
- Provides the termination tools: the failure tool and the blame tool (the blame tool only when blame targets are configured); the advance tool's definition comes from guide_delivery (its parameters follow the step state).
- Per-session state only: the diff and the verification outcome; nothing persists across sessions.
- Verification-callback exceptions are outside the interface contract; this implementation reports them as `ToolFailure[str]` signals with text starting `Verification error: ` (pinned; tests may assert it).

**HLS Justification:** Delegates verification to the injected callback when provided.

## Invariants

- No state persists between runs
- Verification results set the supersession flag; termination results never do
- The feedback-pending gate is checked only when advance would otherwise signal successful termination without a change
- Only valid blame pairs (targets in `blame_targets`) reach the session result

## Non-Concerns

- **Change summary length bounds:** Soft bound pinned to 200 characters, hard bound pinned to 500 characters, grace pinned to 4 rejections per run for each bound; tests may assert the soft/hard rejection messages and the grace transitions (a summary within the hard bound accepted on the advance call after 4 soft-limit rejections; a summary over the hard bound turning `advance` into `TerminateAgentWithFailure` on the advance call after 4 hard-limit rejections).
- **Diff size limit:** The `RunControlConfig` field default is pinned to 1000 characters; the truncation footer is pinned to `... diff truncated: showing <limit> of <full> chars ...`; tests may assert it.
- **`fail` failure value:** `fail` returns `TerminateAgentWithFailure[str]` with its value pinned to `Task failed`; tests may assert it.
- **T_tool resolution:** The implementation resolves `T_tool` (from `tool_provider`) to `str` in failure signals (`ToolFailure[str]`, `TerminateAgentWithFailure[str]`).
- **Error message wording:** error messages identify the violated policy or the failing operation; their exact wording is unspecified.
- **Diff presentation:** the exact rendering of the verification diff and its truncation report is unspecified.
