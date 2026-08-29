# agent_loop_asm

fulfills: agent_loop
imports: agent_loop_config (agent-loop configuration), agent_loop_impl (agent-loop implementation), conversation_history_impl (conversation-history implementation), loop_guard_impl (loop-guard implementation)
terms (from agent_loop): run, conversation, truncated response
terms (from agent_loop_config): agent-loop configuration

## Deltas

- Assembles the concrete agent loop implementation by constructing and wiring conversation_history_impl and loop_guard_impl into agent_loop_impl.
- Instantiates the component with the provided agent-loop configuration.
- Exposes the assembled agent_loop interface for execution without exposing internal component instances.

## Non-concerns

- Assembly construction order: the sequence of constructor calls is an implementation detail.
