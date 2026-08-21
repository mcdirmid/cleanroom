# tool_provider

terms (owned): tool definition, tool result, supersession flag, stub, signal, termination result, tool failure, session

## Purpose

Provides tool definitions and executes tool calls, standardizing how tools are defined, how results are structured, and how termination and tool failure are signaled.

## Terms

- Tool definition: a JSON schema describing a tool's name, parameters, and purpose, in the tool-calling dialect accepted by the language model.
- Tool result: the structured outcome of executing a tool call — the content produced, a supersession flag, and an optional note carrying producer-generated guidance for the model. The note does not replace the content; the consuming agent loop renders it into the model-visible message.
- Supersession flag: whether the result supersedes the earlier non-stubbed result for the same file or tool command; which results carry the flag is declared by the producing component; a result without the flag never supersedes an earlier result.
- Stub: replacing a superseded tool result's content with a static placeholder, preserving the result's position in the conversation; once a result is stubbed, its placeholder never changes for the remainder of the session.
- Signal: the indicator of whether execution continues, terminates, or fails; the signals are continue, terminate the run with success, terminate the run with failure, and tool failure.
- Termination result: the outcome of a successfully terminated session, carried by the successful termination signal: completed with no changes, completed with changes to propagate, or attributed to dependencies with feedback for correction.
- Tool failure: an invalid tool call; the operation is not executed and the session continues.
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
- A tool result never carries the stub text: the stub text appears only when earlier results are replaced in the conversation; a tool failure is never a stub.
- When a result's flag is set, the earlier non-stubbed result for the same file or tool command is stubbed in place with a static stub.
- A stub is static once set: a stubbed result's placeholder never changes for the remainder of the session.
- Each tool call produces exactly one outcome: a tool result, continue, terminate with success, terminate with failure, or tool failure.
- A successful termination signal always carries a termination result; a failure termination signal carries a value describing the failure.
- Termination is atomic: once a termination signal is produced, no further tool results are produced.
- All inputs are validated against the tool's schema before execution; an invalid tool call signals tool failure without executing the operation.
- Errors leave the provider's state unchanged; stubbing preserves the original position of messages in the conversation.
- The flag unset stubs nothing.
- A result supersedes at most one earlier result.
- The provider does not interpret tool results; it produces them.
- May maintain state across tool calls within a single session; no state persists across sessions.

**Assumptions**

- The consumer routes termination signals appropriately and interprets the carried termination result.
- The consumer stubs the earlier result when a result's flag is set, identifying it by the file or tool command the result concerns.

## Non-concerns

- Tool result structure: only the semantic content, the supersession flag, and the note are observable.
