<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - dag_clean_logic.md
  - dag_storage.md
  - file_view.md
  - guide_delivery.md
-->

# Interface LLS: run_control

## Data Types
```python
from dataclasses import dataclass
from typing import Callable, Protocol, TypeAlias
from tool_provider import (
    TerminateAgentWithFailure,
    TerminateAgentWithSuccess,
    TerminateSuccessResult,
    ToolCallOutcome,
    ToolDefinition,
    ToolFailure,
    T_tool,
)
from dag_storage import NodeId, NodeMessage
from dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult
from file_view import VirtualName

BlameTargets: TypeAlias = dict[VirtualName, NodeId]

BlameTarget: TypeAlias = VirtualName

Feedback: TypeAlias = str

Blame: TypeAlias = tuple[BlameTarget, Feedback] | dict[str, str]

VerificationCallback: TypeAlias = Callable[[], tuple[bool, str]] | None

DiffSizeLimit: TypeAlias = int

@dataclass
class RunControlConfig:
    verification_callback: VerificationCallback
    feedback_pending: bool
    blame_targets: BlameTargets
    diff_size_limit: DiffSizeLimit = 1000

class RunControl(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def advance(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome: ...
    def fail(self) -> ToolCallOutcome: ...
    def blame(self, blames: list[Blame]) -> ToolCallOutcome: ...
```

`RunControlConfig` is the client-supplied configuration for verification and termination: an optional verification callback (its success flag gates advance; it may only modify the node's lib/test BUILD file, which is not among the workspace's files), whether the session's pending messages include a feedback message, the blame targets (a mapping from each blameable artifact's virtual name to the node that owns it), and the diff size limit (the maximum characters a verification diff may report; default 1000).

`BlameTarget` is the virtual name of a blameable artifact — a dependency's declared source file, addressed per the virtual name rules; run_control resolves it to the owning node via the configured `blame_targets` mapping. `Feedback` is the correction feedback on how to correct the blamed node's output. Each `Blame` pair corresponds to one feedback message delivered to the owning node.
## Term definitions

- **blame** → term definition: a termination outcome that attributes the task's incompleteness to one or more dependencies and provides feedback on how to correct their outputs; blame is not failure (realized as the `Blame` type)
- **blame target** → the `BlameTarget` alias (definition in Data Types): the virtual name of a blameable artifact — a dependency's declared source file — resolved to its owning node via the configured `blame_targets` mapping
- **soft length bound** → term definition: the preferred maximum length of a change summary; a summary exceeding it is rejected with shortening guidance up to a grace count, then accepted when within the hard length bound (the bound values are pinned in the implementation spec)
- **hard length bound** → term definition: the maximum length a change summary may reach; a summary exceeding it is rejected with hard-bound guidance up to a grace count, and a summary still exceeding it after the grace count fails the session
- **change message** → term definition from dag_clean_logic
- **feedback message** → term definition from dag_clean_logic
- **termination result** → the `TerminateSuccessResult` type from tool_provider
- **tool failure** → the `ToolFailure` type from tool_provider
- **supersession flag** → term definition from tool_provider
- **virtual name** → term definition from file_view
- **guide** → term definition from guide_delivery
- **guide summary** → term definition from guide_delivery
- **step section** → term definition from guide_delivery
- **step mode** → term definition from guide_delivery

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]
```

**Purpose:** Return the termination tools' definitions: the failure tool and the blame tool.

**Preconditions:** run_control has been configured.

**Postconditions:**
- Returns the failure tool's definition (always) and the blame tool's definition (only when blame targets are configured and non-empty)
- The advance tool's definition is provided by guide_delivery (its parameters follow the step state); it is not among run_control's definitions

**Failure Handling:** No failure conditions.

**HLS Justification:** The tool surface composes the components' operations: run_control provides the termination tools.


### `advance`

```python
def advance(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome
```

**Purpose:** Signal the session's completion: verification, step-mode delivery, and termination sequence within the advance. The agent calls this when it has nothing more to do or considers its task complete.

**Preconditions:**
- A file counts as changed only when its current content differs from its content at session start (a write that nets out to no change — e.g., an edit later undone — is not changed)
- The change-message requirement applies only to the terminating advance: in step mode, an advance with step sections remaining carries no change message (per the step mode rules)
- When the session changed files, `changes` must list one entry per changed file — `{"file": <virtual path>, "summary": <one short sentence naming the parts of the file that changed for the next reader; not the task performed, not how it was done>}` — covering every changed file, each summary non-empty and within the summary bound
- A summary exceeding the summary bound is rejected with guidance to shorten it; persistent rejection fails the session

**Postconditions:**
- Verifies the run: computes the diff of the run's changes, truncated when it exceeds the diff size limit (reporting the truncated size and the full change counts); runs the verification callback when one is configured; when no callback is configured, verification is treated as passed
- On a failing verification: returns feedback, never a tool failure, and the session continues; advance never terminates on a failing verification; in step mode, the output is the restated guide summary with the reason verification failed (per guide_delivery's output rule, `get_advance_output`), and the next step section is not delivered; outside step mode, the output is a `ToolResult` with `supersedes` set carrying the verification failure details and guidance to change files and call `advance` again, or call `blame` or `fail` to end the run
- On a passing verification (or no callback): in step mode with step sections remaining, delivers the next step section (per guide_delivery's output rule, `get_advance_output`); with no step sections remaining, proceeds to the termination machinery
- The termination machinery: returns `TerminateAgentWithSuccess` (a `Signal[T_tool]` variant) carrying a `TerminateSuccessResult` describing the session outcome: a `NoChangeResult` when no file's current content differs from its run-start content (writes may have occurred but net out), or a `ChangeResult` whose messages are built from `changes` when files changed
- When `feedback_pending` is set and the run would otherwise signal successful termination without a change (no file's current content differs from its run-start content and no change message is provided), returns `ToolFailure` with a reason directing the agent to change, blame, or fail; the session continues
- Termination tools produce no `ToolResult` and never supersede an earlier result; advance's termination outcome is never a tool failure; the change-message machinery (including the empty-message failure) applies only to the terminating advance

**Failure Handling:**
- In step mode, an advance with step sections remaining never signals a tool failure for the change message: the change-message machinery applies only to the terminating advance.
- A pending feedback message is not disclosed to the agent before advance is attempted without a change; it surfaces only through advance's rejection (per the termination rules).
- Run changed files and `changes` empty → Return `ToolFailure[T_tool]` listing the changed files and showing the run's diff, instructing the agent to call `advance` again with one `{file, summary}` entry per changed file (one short sentence on what changed, not how) or to call `fail`/`blame` to end the run.
- An entry with a missing/empty `file` or `summary` → `ToolFailure[T_tool]` requiring both fields.
- An entry naming a file the run did not change → `ToolFailure[T_tool]` naming the changed files.
- A claimed change for a run whose writes all net out to no change (every written file's current content equals its run-start content) → `ToolFailure[T_tool]` stating the run net-changed nothing and directing `advance()` with no changes to report no change.
- A summary exceeding the summary bound → `ToolFailure[T_tool]` directing the agent to shorten the summary and call `advance` again; persistent rejection turns `advance` into failure.
- A changed file with no entry → `ToolFailure[T_tool]` listing the uncovered files.
- `feedback_pending` set and advance without a change (no net-changed files, no change message) → `ToolFailure[T_tool]` with a reason directing the agent to change, blame, or fail; the session continues.
- Verification callback throws exception → Callback error is unhandled (no contract specified in this interface spec).

**HLS Justification:** Advance signals successful termination when verification passes, provides feedback (never a tool failure) on a failing verification, and requires a change summary when the run changed files.


### `fail`

```python
def fail(self) -> ToolCallOutcome
```

**Purpose:** End the session in failure. The agent calls this when it considers the task cannot be completed.

**Preconditions:** No termination signal has been produced yet in the current session.

**Postconditions:**
- Returns `TerminateAgentWithFailure[T_tool]` (a `Signal[T_tool]` variant); the session terminates in failure.
- A correctly-invoked `fail` is not a `ToolFailure` — `ToolFailure` signals a failed call.
- Termination tools produce no `ToolResult` and never supersede an earlier result.

**Failure Handling:**
- No expected failures: a correctly-invoked `fail` always signals termination.
- Invoking `fail` after a termination signal has been produced violates the terminal precondition (undefined behavior).

**HLS Justification:** The failure operation ends the session in failure.


### `blame`

```python
def blame(self, blames: list[Blame]) -> ToolCallOutcome
```

**Purpose:** Signal termination with blame: attribute the task's incompleteness to dependencies and provide feedback on how to correct their outputs. The agent calls this when it considers the task incomplete and attributes the incompleteness to specific dependencies.

**Preconditions:**
- Blame targets are configured (non-empty)
- Each pair's target must be a key of `blame_targets` (a blameable artifact's virtual name)

**Postconditions:**
- If all pairs are valid: returns `TerminateAgentWithSuccess` (a `Signal[T_tool]` variant) carrying a `TerminateSuccessResult` that describes feedback to dependencies (a `FeedbackResult`; one (target, feedback) pair per blamed dependency, each target resolved to its owning node's `NodeId` via `blame_targets`)
- If any pair's target is not a key of `blame_targets`: returns `ToolFailure[T_tool]` naming the invalid target and listing the valid blame targets (the keys of `blame_targets`)
- Each pair corresponds to one feedback message (a `NodeMessage` with the feedback kind) delivered to its owning node (per the feedback message rules)
- Termination tools produce no `ToolResult` and never supersede an earlier result

**Failure Handling:**
- Invalid pairs (targets not keys of `blame_targets`): Return `ToolFailure[T_tool]` (a `Signal[T_tool]` variant) with an error message identifying the invalid target and listing the valid blame targets by their virtual names.
- Empty `blames` list: Return `ToolFailure[T_tool]` with an error message describing the empty list.
- Blame targets not configured is a precondition violation (unexpected); the interface does not prescribe violation behavior (`blame` is not provided in the tool definitions when targets are empty).

**HLS Justification:** "Blame."

## Invariants

- Verification runs as part of the advance operation; verification passes when no verification callback is configured
- A failing verification never terminates the run: the session continues with feedback
- Advance never signals a tool failure for the change message while step sections remain (per the step mode rules)
- The change-message requirement applies only to the terminating advance
- The feedback-pending gate is checked only when advance would otherwise signal successful termination without a change; a failing verification and the change-message requirement are checked first
- Termination tools never produce `ToolResult` and never supersede an earlier result
- Each (target, feedback) pair of a blame is delivered as a feedback message to the blamed artifact's owning node
- The verification callback, if provided, has no side effects on the workspace; it may only modify the node's lib/test BUILD file (maintained by the build linter), which is not among the workspace's files
- No state persists across runs

## Non-Concerns

- **Advance tool description:** the advance tool's description wording is unspecified; the tool's contract is defined by the verification, termination, and step-mode rules.
- **Bound values:** the soft and hard length bound values and the grace count are unspecified here; they are pinned in the implementation spec.
- **Error message wording:** error messages identify the violated policy or the failing operation; their exact wording is unspecified.
- **Net-out change claims:** the HLS rejects "missing, malformed, or incomplete" change summaries; a run whose writes all net out to no change is narrowed here to report no change (the change-message requirement applies only when the filesystem differs from run start).
- **Blame failures:** the HLS pins blame as offered when blame targets are configured; the failure signals for an invalid blame target or an empty `blames` list are pinned here (expected failures are return signals).
