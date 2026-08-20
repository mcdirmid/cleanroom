# tool_provider

terms (owned): tool definition, tool result, content ID, stub, signal, termination result, tool failure, session

## Purpose

Provides tool definitions and executes tool calls, standardizing how tools are defined, how results are structured, and how termination and tool failure are signaled.

## Owned definitions

- Tool definition: a JSON schema describing a tool's name, parameters, and purpose, in the tool-calling dialect accepted by the language model.
- Tool result: the structured outcome of executing a tool call — the content produced, a content ID for deduplication, a flag indicating whether previous results with the same content ID are hidden, and an optional note carrying producer-generated guidance for the model (e.g., how much content remains and how to continue). The note does not replace the content; the consuming agent loop renders it into the model-visible message.
- Content ID: the identifier of a tool result's content for deduplication, or none when the result is never stubbed.
- Stub: replacing a previous tool result's content with a placeholder while preserving its position in the conversation.
- Signal: the indicator of whether execution continues, terminates, or fails; the signals are continue, terminate the run with success, terminate the run with failure, and tool failure.
- Termination result: the outcome of a successfully terminated session, carried by the successful termination signal: completed with no changes, completed with changes to propagate, or attributed to dependencies with feedback for correction.
- Tool failure: an invalid tool call; the operation is not executed and the session continues.

## Observable dataflow

- Inputs per tool call: the tool name and the tool arguments.
- Outputs: the tool-definition list; per call, exactly one outcome — a tool result, continue, terminate with success (carrying a termination result), terminate with failure (carrying a failure value), or tool failure.
- Termination is atomic: once a termination signal is produced, no further tool results are produced.
- The provider may maintain state across tool calls within a single session; no state persists across sessions.
- Stubbing: when a result's flag is true, all previous non-stubbed results with the same content ID are stubbed before the new result is produced; when false, previous results are unchanged. Stubbing preserves message positions.
- The provider does not interpret tool results — it produces them. The consumer routes signals and interprets the carried termination result.

## Contract

**For each tool call, the client provides:**

- The tool name and the tool arguments.

**The client may:**

- Request the list of available tool definitions.
- Execute a tool call.

**The component guarantees:**

- Tool definitions conform to the schema format defined by this interface.
- Tool results contain the content, the content ID (or none), and the stub flag.
- When the stub flag is true, all previous non-stubbed results with the same content ID are stubbed before the new result is produced; when false, previous results remain unchanged.
- Each tool call produces exactly one outcome: a tool result, continue, terminate with success, terminate with failure, or tool failure.
- A successful termination signal always carries a termination result; a failure termination signal carries a value describing the failure.
- All inputs are validated against the tool's schema before execution; an invalid tool call signals tool failure without executing the operation.
- Errors leave the provider's state unchanged; stubbing preserves the original position of messages in the conversation.

**The component assumes:**

- The consumer routes termination signals appropriately and interprets the carried termination result.
- The consumer maintains the mapping between content IDs and results for stubbing.

## Non-concerns

- Content ID structure: the internal format of content ID values within a single session.
- Tool result structure: only the semantic content, content ID, and stub flag are observable.
