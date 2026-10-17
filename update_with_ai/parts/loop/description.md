# Loop Part (`update_with_ai/parts/loop`)

## Purpose

The **loop** part implements the autonomous, multi-turn pair-programming execution loop that drives language models to clean dirty DAG nodes.

Executing software tasks with language models requires managing conversation state across multiple turns, dispatching tool calls, detecting unproductive repetition or file-editing oscillations, handling unexpected crashes, and translating session outcomes (success, failure, or blame) back into persistent DAG state updates. The loop part formalizes the conversation lifecycle, loop guard tripwires, turn drivers, and node cleaners that together enable robust in-process agent execution.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/loop/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high):

- [`loop.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop.md): Defines foundational types and lifecycle contracts for the execution loop.
- [`loop_cleaner.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop_cleaner.md): Scopes an active subgraph from a target node, iterates through ready node batches in dependency-first topological order, records node visits, and concludes when the target subgraph is complete in DAG storage.
- [`loop_node_cleaner.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop_node_cleaner.md) & [`loop_node_cleaner_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop_node_cleaner_impl.md): Executes task workloads for dirty nodes sharing a role. It seeds conversation history with `get_work` instructions, invokes the loop driver, logs unexpected execution failures with automatic single-retry handling, and resolves session outcomes into DAG storage: marking nodes clean with change summaries when files are modified, marking them clean without advancing change timestamps when files are untouched, or recording unacted feedback addressed strictly to blamed upstream targets.
- [`loop_driver.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop_driver.md): Coordinates the turn-by-turn interaction between the language model, installed session tools, the loop guard, and the runner logger until target submission, blame attribution, or fatal failure occurs.
- [`loop_conversation.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop_conversation.md): Manages structured conversation history. It translates internal session events into model-visible messages, correlates tool results with model invocations, formats active reminders and notes, and synthesizes assistant tool call stubs for unprompted initial tool responses.
- [`loop_guard.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop_guard.md) & [`loop_guard_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop_guard_impl.md): Monitors turns for unproductive loops and oscillations. It tracks consecutive executions of identical tools with identical arguments and consecutive edits to the same file and line span. It issues advisory loop reminders at warning thresholds (two repetitions) advising that repeated tool execution without modifying files will trigger termination, and raises fatal loop failures to abort runaway loops when fatal thresholds are breached. It resets counters upon genuine forward progress.
- [`loop_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop_asm.md): Assembles the loop cleaner, node cleaner, and loop guard into an operational loop subsystem.

## How It Is Used by Other Parts

- **`openai`**: Realizes the abstract `loop_driver` and `loop_conversation` contracts for OpenAI-compatible chat completion endpoints (`openai_driver_impl` and `openai_conversation_impl`).
- **`uv`**: Provides `uv_loop_impl`, which instantiates the loop cleaner and node cleaner to run in-process Cleanroom loops for Python UV targets.
- **`systems`**: Aggregated into `uv_openai_loop_asm` to form the runnable in-process agent execution engine.
- **`support` (`cleanroom_uv_runner`)**: Invokes the loop subsystem via `uv_loop_impl` when running `cleanroom-loop` to clean dirty project nodes.
