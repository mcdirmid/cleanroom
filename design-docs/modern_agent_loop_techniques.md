# Guide: Building an Agent Loop from a Low-Level Prompt API

An LLM API (OpenAI, Anthropic, Gemini) gives you a response — text or tool calls.
An agent loop is a program that repeatedly feeds that response back in, calling tools
and reading results, until a goal is reached. The quality of your loop determines whether
the agent succeeds or spirals into redundant calls.

## The Core Pattern

```
tool_call = model(messages)
if tool_call:
    result = call_tool(tool_call)
    messages.append(tool_call)
    messages.append(result)
else:
    return text_response
```

The model outputs a tool call or text. The runtime executes the tool, appends both to
the conversation, and calls the model again. Repeat until the model stops calling tools
or an explicit termination condition is met.

This is the ReAct loop (reason, act, observe, repeat). Every coding agent, support bot,
and data pipeline in 2026 runs on a variant of this pattern.

## Prompt Layers

An agent's prompt is a stack of prompts layered by authority:

1. **Platform instructions** — the model's built-in safety and policy constraints (set by
   the provider, invisible to you).
2. **System prompt** — your primary control point. Sets goals, constraints, tool-use
   expectations, and behavioral rules.
3. **Per-tool instructions** — names, descriptions, schemas, and examples embedded in the
   tool definitions themselves.
4. **User prompt** — the concrete request the user submitted (e.g., "Fix the race
   condition in `agents/tasks.py`").
5. **Environment state** — what the model sees in the conversation history.

Each layer matters equally. A great system prompt fails if the tools are poorly described.
Design each layer explicitly.

## Tool Design for Agents

Agent-facing tools are a different category of software.

### Namespacing

Group related tools under consistent prefixes: `editor.read_file`,
`editor.write_file`, `editor.apply_diff`. Avoid deep hierarchies — two to four levels
of namespace is sufficient.

### Verbosity

Agent-facing names tend toward the verbose and explicit: `read_file(path)` is a model
that can infer purpose from the name; `rd()` (ambiguous) leads to errors.
Descriptions should be specific: "execute a bash command in a sandboxed environment and
return stdout and stderr" beats "run a command."

### Return meaningful context

If a tool creates a file, return the path, size, and hash. If a tool searches a database,
return row count and sample results. Return enough information for the agent to verify
*done*, not just *tried*.

### Few, general tools beat many, specific tools

The most successful coding agents use 3–5 tools. Claude Code's core tool is a shell
editor. Devin has shell, code editor, and browser. "Write a file" beats "write file" +
"append file" + "create file."

This rule applies when general tools are available. If the agent is sandboxed (freely
reads files but does not have direct access to the actual filesystem, language runtimes,
or a shell), general-purpose tools are not usable — there is no shell, nothing useful
to do on an arbitrary filesystem, no code you can execute — and you must give the agent
tools that directly express what it is trying to do. In that case, 5–11 task-specific
tools is normal, and the counterintuitive claim is inverted: few specific tools (rather
than few general tools) is the best you can do.

## Memory Management

The conversation history (turns sent back to the model) is a bounded resource with
three capacities — context window, context budget (which may be less than the
window), and billing budget (which may be less than the window or budget). All
three shrink as tokens accumulate.

Available techniques:

- **Context window** (model-limited). If you fit within it, great. Running out
  means calling the API with a 400 error.
- **Context budget** (agent-limited). Application-specific limits smaller than
  the model's window. Incrementally overwrite sections rather than rebuilding
  from scratch.
- **Billing budget** (application-limited). Most budget-efficient when capped
  per run. Over-prompting costs real money.

Treat budget as a hard constraint. An agent that chews through tokens
inefficiently often continues to do so across multiple runs.

## Termination Conditions

You need some signal for when to stop. Strong signals — defined in the tool set
(a tool explicitly returns a FinalAnswer or Terminate) — should be treated as
truly strong results, passed through unchanged. Weak signals (the agent deciding
on its own that it's done) should trigger a guard-rail check: "does this decision
contradict the initial prompt?"

Every run should ask: did the agent answer what was asked, or did it wander?

## Testing and Evaluation

How you test agents is often more important than the tests themselves. Without a
systematic evaluation, you cannot tell whether a tool change improved things.

Standard approaches:

- **Unit tests** against tools (do they behave correctly when invoked?)
- **End-to-end scenarios** (does the agent complete a task given a starting state?)
- **Regression runs** (does the same task still complete after tool changes?)

Cover the modes: single-agent (reasoning within context window) and long-horizon
(multiple runs across context windows, which requires persistent state).

## Failure Modes and Fixes

A useful compendium for debugging:

- **The agent one-shots the task** (tries to do too much at once) — break the task
  into a feature list or subtasks, or have a separate initialization agent scaffold
  the environment.
- **The agent declares victory prematurely** (marks a task "done" without testing) —
  require explicit end-to-end verification before marking any feature complete.
- **The agent forgets what it was doing** (states accumulate across many context
  windows) — commit a progress file (Git logs, a progress note) that the next run
  reads and interprets before acting.
- **The agent repeats the same call** — prompt it to list its own output before
  generating a new call (self-verification).
- **The agent ignores tools entirely** — check that the system prompt invites tool
  use (and does not explicitly exclude it).

## Counter-Intuitive Discoveries

These decisions go against common sense but bear out in practice:

- Overly explicit prompts produce worse results; constraints and boundaries, not
  content instructions, produce better behavior.
- Gritting your teeth and letting the agent fail is often superior to "fixing" its
  errors (which can overwrite useful but ephemeral state).
- Fewer turns + higher-quality responses outperform many turns + lower-quality ones.
- Frequently updating the agent with the user's own words ("Fix the race condition")
  is more effective than elaborating what the user might have meant.

## Practical Checklist

Verify each run:

- [ ] Single agent, single unbounded loop (multi-agent adds complexity without benefit).
- [ ] Single unbounded loop (the agent executes tools itself).
- [ ] No secondary agent constraints (the user provides the prompt).
- [ ] All expected tools are present (and only expected tools are present).
- [ ] Tool definitions specify purpose, constraints, expected behavior, and parameter types.
- [ ] User text matches what the user entered (no rewriting).

Follow the loop once. Write the file once. Read it once. Keep the guide to 20,000 bytes
so a single read captures it all.
