# dag_clean_logic

imports: dag_storage (graph topology for routing intents), tool_provider (termination-result types)
terms (from dag_storage): node, dependency, pending message
terms (from tool_provider): termination result
terms (owned): dirty, cleaning, change message, feedback message, routing intent

## Purpose

Provides the logic that processes pending messages during cleaning: decides when a node is dirty and produces change or feedback messages with routing intent.

## Owned definitions

- Dirty: the state of requiring cleaning. A node is dirty when it has pending messages or custom conditions hold; a node becomes dirty when it receives a change or a feedback message. Custom conditions may flag a node dirty with no pending messages.
- Cleaning: the process of consuming a node's pending messages and producing new messages. A node that produces no messages on being cleaned was successfully cleaned but did not change.
- Change message: informs reverse dependencies how the source node changed.
- Feedback message: informs a specific dependency how it must be updated so cleaning can proceed past the node. A feedback message targets exactly one dependency of the source node. Multiple feedback messages may be produced during a single cleaning, each delivered individually.
- Routing intent: which kind of message is produced and toward whom; routing itself is the consuming component's responsibility.

## Observable dataflow

- Input: cleaning invoked on a node with its pending messages; a dirtiness query for a node.
- Output: on success, zero or more messages for delivery; on failure, no messages and the pending messages unchanged.
- A node produces either change messages or feedback messages during a single cleaning, not both. Producing a feedback message indicates a dependency must be fixed; the current node is cleaned again after the dependency sends a change message.
- All pending messages of the node are processed; success is signaled only after all are processed.
- A successful cleaning result (change, feedback, or no-change) is a termination result per tool_provider: a successful termination signal may carry it.

## Contract

**The client may:**

- Invoke cleaning on a node with its pending messages.
- Query whether a node is dirty.

**The component guarantees:**

- Signals success only after fully processing all messages.
- Signals failure, leaving pending messages unchanged, only when unable to process; no messages are produced.
- Produced messages are valid for delivery.
- Signals dirtiness when the node has pending messages or custom conditions hold.

**The component assumes:**

- The component can identify a node's dependencies (from the graph topology) to form routing intents.

## Non-concerns

- Error propagation details: how failures propagate between components is unspecified.
