# Loop Part (`update_with_ai/parts/loop`)

## Purpose

The **loop** part implements the autonomous, multi-turn pair-programming execution loop that drives language models to clean dirty DAG nodes.

Executing software tasks with language models requires managing conversation state across multiple turns, dispatching tool calls, detecting unproductive repetition or file-editing oscillations, handling unexpected crashes, and translating session outcomes (success, failure, or blame) back into persistent DAG state updates. The loop part formalizes the conversation lifecycle, loop guard tripwires, turn drivers, and node cleaners that together enable robust in-process agent execution.

## Key Components & Specifications

According to the high-level specifications in [`update_with_ai/parts/loop/high/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high):

- [`loop.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop.md): Defines foundational types and lifecycle contracts for the execution loop.
- [`cleaner.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/cleaner.md): Scopes an active subgraph from a target node, iterates through ready node batches in dependency-first topological order, records node visits, and concludes when the target subgraph is complete in DAG storage.
- [`node_cleaner.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/node_cleaner.md) & [`node_cleaner_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/node_cleaner_impl.md): Executes task workloads for dirty nodes sharing a role. It seeds conversation history with `get_work` instructions, invokes the loop driver, logs unexpected execution failures with automatic single-retry handling, and resolves session outcomes into DAG storage: marking nodes clean with change summaries when files are modified, marking them clean without advancing change timestamps when files are untouched, or recording unacted feedback addressed strictly to blamed upstream targets.
- [`driver.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/driver.md): Coordinates the step-by-step interaction between the language model, installed session tools, the loop guard, and the runner logger until target submission, blame attribution, or fatal failure occurs.
- [`conversation.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/conversation.md): Manages structured conversation history. It translates internal session events into model-visible messages, correlates tool results with model invocations, formats active reminders and notes, and synthesizes assistant tool call stubs for unprompted initial tool responses.
- [`guard.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/guard.md) & [`guard_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/guard_impl.md): Monitors steps for unproductive loops and oscillations. It tracks consecutive executions of identical tools with identical arguments and consecutive edits to the same file and line span. It issues advisory loop reminders at warning thresholds (two repetitions) advising that repeated tool execution without modifying files will trigger termination, and raises fatal loop failures to abort runaway loops when fatal thresholds (four repetitions) are breached. It resets counters upon genuine forward progress.
- [`logger.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/logger.md) & [`logger_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/logger_impl.md): Provides execution event logging. It formats compact single-line summaries for live terminal visibility while immediately flushing verbose event records to an unbuffered disk transcript log (defaulting to `agent_loop.log`) to preserve audit history across process crashes.
- [`loop_asm.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop_asm.md): Assembles the loop cleaner, node cleaner, loop guard, and runner logger into an operational loop subsystem.

## How It Is Used by Other Parts

- **`openai`**: Realizes the abstract `driver` and `conversation` contracts for OpenAI-compatible chat completion endpoints (`driver_impl` and `conversation_impl`).
- **`uv`**: Provides `loop_impl`, which instantiates the loop cleaner and node cleaner to run in-process Cleanroom loops for Python UV targets.
- **`systems`**: Aggregated into `openai_loop_asm` to form the runnable in-process agent execution engine.
- **`support` (`cleanroom_uv_runner`)**: Invokes the loop subsystem via `loop_impl` when running `cleanroom-loop` to clean dirty project nodes.
