# tool_provider

terms (owned): tool definition, tool result, presented tool result, supersession flag, stub, signal, termination result, tool failure, session, tool call

## Purpose

Provides tool definitions and executes tool calls, standardizing how tools are defined, how results are structured, and how termination and tool failure are signaled.

## Terms

- Tool call: an invocation requested by the model naming a tool and its arguments.

- Tool definition: a JSON schema describing a tool's name, parameters, and purpose, in the tool-calling dialect accepted by the language model.
- Tool result: a structured outcome produced by executing a tool call — the content produced, a supersession flag, and an optional note carrying producer-generated guidance for the model. The note does not replace the content; the consuming agent loop renders it into the model-visible message.
- Presented tool result: a tool result as presented to the agent — the tool result plus the tool's name and arguments, for attribution by the consuming agent loop.
- Supersession flag: whether the result supersedes the earlier non-stubbed result for the same file or tool command; which results carry the flag is declared by the producing component; a result without the flag never supersedes an earlier result.
- Stub: replacing a superseded tool result's content with a placeholder.
- Signal: the indicator of whether execution continues, terminates, or fails; the signals are continue, terminate the run with success, terminate the run with failure, and tool failure.
- Termination result: the outcome of a successfully terminated session, carried by the successful termination signal: completed with no changes, completed with changes to propagate, or attributed to dependencies with feedback for correction.
- Tool failure: a signal that a tool call could not do meaningful work — wrong arguments, wrong format, an unknown tool, a policy violation, or a termination tool invoked incorrectly; the operation is not executed and the session continues.
- Session: the sequence of tool calls and outcomes of a single run, continuing until a termination signal is produced.

## Contract

**Inputs**

- Per tool call: the tool name and the tool arguments.

**Operations**

- Request the list of available tool definitions.
- Execute a tool call.

**Guarantees**

- Provides the tool-definition list.
- Tool definitions conform to the schema format defined by this interface.
- Tool results contain the content, the supersession flag, and the note.
- A tool result is presented to the agent as a presented tool result: the result plus the tool's name and arguments.
- When a result's flag is set, the earlier non-stubbed result for the same file or tool command is replaced by a static stub.
- Each tool call produces exactly one outcome: one or more tool results, or a signal — continue, terminate with success, terminate with failure, or tool failure.
- A successful termination signal always carries a termination result; a failure termination signal carries a value describing the failure.
- Termination is atomic: once a termination signal is produced, no further tool results are produced.
- All inputs are validated against the tool's schema before execution; an invalid tool call signals tool failure without executing the operation.
- A tool failure signals an immediate problem that prevented meaningful work.
- A rejected result with feedback is a tool result, never a tool failure.
- Errors leave the provider's state unchanged.
- The flag unset stubs nothing.
- A result supersedes at most one earlier result.
- The provider does not interpret tool results; it produces them.
- May maintain state across tool calls within a single session; no state persists across sessions.

**Assumptions**

- The consumer routes termination signals appropriately and interprets the carried termination result.
- The consumer stubs the earlier result when a result's flag is set, identifying it by the file or tool command the result concerns.

## Non-concerns

- Tool result structure: only the semantic content, the supersession flag, the note, and the presented form's name and arguments (per presented tool result) are observable.
