"""
tests/agent_loop_driver.py

Driver script for testing agent_loop_impl against real models.
Not a test - runs actual agent loops with real API calls.
"""

import json
import datetime
from typing import cast, Any, Dict, List

from update_with_ai.lib.agent_loop import AgentLoopConfig
from update_with_ai.lib.agent_loop_impl import AgentLoopImpl
from update_with_ai.lib.agent_loop import (
    ToolCall,
    ToolDefinition,
    LoggerCallback,
    LogEvent,
    Usage,
    CumulativeUsage,
)
from update_with_ai.lib.dag_clean_logic import ChangeResult
from update_with_ai.lib.tool_provider import (
    ToolResult,
    ToolCallOutcome,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
)


# ============================================================
# Configuration
# ============================================================

config = AgentLoopConfig(
    base_url="http://localhost:8000/v1",
    api_key="abcd",
    model="stamsam-Qwen3.6-35B-A3B-Q4",
    max_iterations=5,
    temperature=0.7,
    timeout=60.0,
    max_tokens=4096,
    termination_reminder_generator=None,  # Optional: set to enable termination
)


# ============================================================
# Tool Definitions
# ============================================================

def get_weather_tool() -> ToolDefinition:
    """Define a simple weather tool."""
    return cast(ToolDefinition, {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name, e.g., 'San Francisco'",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit",
                    },
                },
                "required": ["location"],
            },
        },
    })


def get_time_tool() -> ToolDefinition:
    """Define a simple time tool."""
    return cast(ToolDefinition, {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time for a timezone",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone, e.g., 'America/New_York'",
                    },
                },
                "required": [],
            },
        },
    })


def succeed_tool() -> ToolDefinition:
    """Define the termination tool: the session ends only via succeed()/fail()."""
    return cast(ToolDefinition, {
        "type": "function",
        "function": {
            "name": "succeed",
            "description": (
                "Signal successful termination, carrying the change message "
                "for the next reader (one short sentence on what changed; "
                "there is no free-text final answer — you must call succeed() "
                "or fail() to end the run)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "One short sentence on the answer or what changed",
                    },
                },
                "required": ["summary"],
            },
        },
    })


def fail_tool() -> ToolDefinition:
    """Define the failure termination tool."""
    return cast(ToolDefinition, {
        "type": "function",
        "function": {
            "name": "fail",
            "description": "Signal failure and end the run.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    })


# ============================================================
# Tool Executor
# ============================================================

def tool_executor(name: str, arguments: Dict[str, Any]) -> ToolCallOutcome[str]:
    """Execute a single tool call and return a ToolResult (per-call ToolExecutor).

    Weather lookups never supersede (read-only observations). Time lookups
    supersede the earlier time result, so re-querying stubs the previous
    result instead of accumulating copies in the conversation.
    """
    if name == "get_weather":
        location = arguments.get("location", "unknown")
        unit = arguments.get("unit", "celsius")
        if unit == "celsius":
            temp = 22
            unit_str = "°C"
        else:
            temp = 72
            unit_str = "°F"
        result = f"Weather in {location}: {temp}{unit_str}, partly cloudy"
        return ToolResult(
            content=json.dumps({"weather": result}),
            supersedes=False,
            note=f"Weather lookup for {location}",
        )

    if name == "get_current_time":
        current_time = datetime.datetime.now().isoformat()
        return ToolResult(
            content=json.dumps({"time": current_time}),
            supersedes=True,
            note="Current time",
        )

    if name == "succeed":
        # There is no free-text final answer: the session ends only via a
        # termination tool. The change message is the only completion artifact.
        summary = arguments.get("summary", "Answered the prompt")
        return TerminateAgentWithSuccess(ChangeResult(messages=[summary]))

    if name == "fail":
        return TerminateAgentWithFailure[str]("Task failed")

    return ToolResult(
        content=json.dumps({"error": f"Unknown tool: {name}"}),
        supersedes=False,
    )


# ============================================================
# Logger Callback - Shows All Features
# ============================================================

def logger_callback(event: LogEvent, data: dict[str, Any]) -> None:
    """Log agent execution events with full token tracking."""

    if event == "message_added":
        msg = data.get("message", {})
        role = msg.get("role", "unknown")
        content = msg.get("content")
        if content is not None:
            preview = str(content)[:100] + "..." if len(str(content)) > 100 else content
            print(f"  [LOG] Message ({role}): {preview}")
        else:
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                names = [tc.get("function", {}).get("name", "unknown") for tc in tool_calls]
                print(f"  [LOG] Message ({role}): tool_calls={', '.join(names)}")
            else:
                print(f"  [LOG] Message ({role}): (no content)")

    elif event == "message_stubbed":
        stubbed = data.get("stubbed_message", {})
        content = str(stubbed.get("content", ""))
        preview = content[:60] + "..." if len(content) > 60 else content
        print(f"  [LOG] Message stubbed: {preview!r}")

    elif event == "tool_called":
        tool_calls = data.get("tool_calls", [])
        names = [tc.get("function", {}).get("name", "unknown") for tc in tool_calls]
        args = [tc.get("function", {}).get("arguments", "{}") for tc in tool_calls]
        print(f"  [LOG] Tool(s) called: {', '.join(names)}")
        for name, arg in zip(names, args):
            print(f"       {name}({arg[:50]}...)")

    elif event == "tool_result":
        results = data.get("results", [])
        print(f"  [LOG] Tool result(s): {len(results)} returned")
        for r in results:
            supersedes = getattr(r, 'supersedes', False)
            print(f"       supersedes={supersedes}")

    elif event == "api_response":
        usage = data.get("usage", {})
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = usage.get("total_tokens", 0)
        print(f"  [TOKENS] Context: {prompt:,} tokens | Response: {completion:,} | Cost: {total:,} tokens")

    elif event == "reminder_injected":
        message = data.get("message", "")
        print(f"  [LOG] Reminder injected: {message}")

    elif event == "run_terminated":
        termination_value = data.get("termination_value", "unknown")
        usage = data.get("usage", {})
        cumulative = data.get("cumulative_usage", {})
        final_context = data.get("final_context_size", 0)

        print(f"  [LOG] Run terminated: {termination_value}")
        print(f"  [TOKENS] Final context size: {final_context:,} tokens")
        print(f"  [TOKENS] Total spent: {cumulative.get('total_tokens', 0):,} tokens")
        print(f"  [TOKENS]   - Prompt tokens: {cumulative.get('prompt_tokens', 0):,}")
        print(f"  [TOKENS]   - Completion tokens: {cumulative.get('completion_tokens', 0):,}")
        print(f"  [TOKENS]   - API calls: {cumulative.get('request_count', 0)}")

    elif event == "error":
        error = data.get("error", "unknown error")
        usage = data.get("usage")
        cumulative = data.get("cumulative_usage")
        last_context = data.get("last_context_size")

        print(f"  [LOG] ERROR: {error}")
        if last_context is not None:
            print(f"  [TOKENS] Context size at failure: {last_context:,} tokens")
        if cumulative:
            print(f"  [TOKENS] Spent {cumulative.get('total_tokens', 0):,} tokens before failure")
            print(f"  [TOKENS] API calls before failure: {cumulative.get('request_count', 0)}")


# ============================================================
# Run the Agent
# ============================================================

def main():
    agent = AgentLoopImpl(config=config)

    system_prompt = (
        "You are a helpful assistant with tools for weather and time lookups. "
        "A new time lookup replaces the earlier time result in the "
        "conversation; weather lookups are never replaced. Line numbers are "
        "metadata, not content. There is no free-text final answer: when you "
        "have answered, call succeed() (with a one-sentence summary) or "
        "fail() to end the run."
    )

    prompts = [
        "What's the weather in San Francisco?",
        "What's the current time?",
        "What's the weather in London and what time is it there?",
        "What's the weather in Paris? Actually, wait, I meant Paris, France. What's the weather there?",
        "What's the weather in Tokyo and what's the weather in Berlin?",
        "What time is it? And what time is it now?",
    ]

    tools: List[ToolDefinition] = [
        get_weather_tool(),
        get_time_tool(),
        succeed_tool(),
        fail_tool(),
    ]

    print("\n" + "=" * 70)
    print("AGENT LOOP DEMO WITH STATIC STUBBING & TOKEN TRACKING")
    print("=" * 70)
    print("\nNOTE: Results supersede per the tool's declaration.")
    print("  - Weather: never supersedes (appended to the conversation)")
    print("  - Time: supersedes the earlier time result; the earlier result")
    print("    is stubbed in place with a static placeholder")

    for i, prompt in enumerate(prompts, 1):
        print(f"\n{'=' * 70}")
        print(f"Test #{i}")
        print(f"Prompt: {prompt}")
        print('-' * 70)

        result = agent.run_agent(
            prompt=prompt,
            tools=tools,
            tool_executor=tool_executor,
            system_prompt=system_prompt,
            logger=logger_callback,
        )

        print('-' * 70)

        # Handle result: (signal, history) termination tuples, or
        # (error, history) loop failures. There is no free-text final answer.
        if isinstance(result, tuple):
            signal, history = result
            if isinstance(signal, TerminateAgentWithSuccess):
                print(f"Terminated (success)!\nValue: {signal.value}")
            elif isinstance(signal, TerminateAgentWithFailure):
                print(f"Terminated (failure)!\nValue: {signal.value}")
            else:
                print(f"Loop failure!\nError: {signal}")
        else:
            print(f"Unknown result type: {type(result)}")
            history = []

        print(f"History length: {len(history)} messages")

        tool_msgs = [m for m in history if m.get("role") == "tool"]
        if tool_msgs:
            print(f"   Tool messages: {len(tool_msgs)}")
            for m in tool_msgs:
                content_preview = str(m.get("content", ""))[:60]
                print(f"     {content_preview}...")
        print('=' * 70)

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
