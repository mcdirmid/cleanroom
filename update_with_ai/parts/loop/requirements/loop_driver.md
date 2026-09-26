# loop_driver interface component

imports: loop_conversation, loop_guard, agent_config, runner_logger, tool_provider

## Assumptions and Requirements

### Requirements

1. The loop driver drives turns by sending model requests to a language model and executing requested tools.
2. The loop driver appends model responses and correlates tool responses with tool call identifiers in the conversation.
3. The loop driver can dispatch follow-up tool calls specified by tool responses, recording the follow-up execution in the conversation.
4. The loop driver records log events for interaction turns, tool executions, and turn outcomes to the runner logger.
5. The loop driver evaluates tool executions with the loop guard, injecting reminders or halting with an unexpected failure on runaway repetition.
6. When a model response contains no tool executions, the loop driver injects a tool reminder into the conversation and continues the turn loop.
7. When tool execution produces a termination outcome, the loop driver concludes and returns a loop outcome, or halts with an unexpected failure if the termination indicates a failing outcome.
8. When the conversation limit from agent config is exceeded, the loop driver halts with an unexpected failure.

## Grounding Facts

### Knowledge Needed

- Model requests and tool specifications.
- Tool responses and correlation identifiers.
- Follow-up tool call directives.
- Conversation limit from `agent_config`.
- Loop repetition signals from `loop_guard`.

### Actions Needed

- Drive interaction turns with language model.
- Execute tools and correlate responses in conversation.
- Record log events to `runner_logger`.
- Guard against repetition loops with `loop_guard`.
- Return loop outcome or signal unexpected failure.
