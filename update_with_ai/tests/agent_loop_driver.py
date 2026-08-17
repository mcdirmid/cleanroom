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
    FinalAnswer,
)
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


# ============================================================
# Tool Executor
# ============================================================

def tool_executor(name: str, arguments: Dict[str, Any]) -> ToolCallOutcome[str]:
    """Execute a single tool call and return a ToolResult (per-call ToolExecutor)."""
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
            content_id=f"weather_{location.lower()}",
            stub_previous=True,
        )

    if name == "get_current_time":
        current_time = datetime.datetime.now().isoformat()
        return ToolResult(
            content=json.dumps({"time": current_time}),
            content_id="current_time",
            stub_previous=True,
        )

    return ToolResult(
        content=json.dumps({"error": f"Unknown tool: {name}"}),
        content_id=None,
        stub_previous=False,
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
        content_id = data.get("content_id", "unknown")
        stubbed = data.get("stubbed_message", {})
        replacement = data.get("replacement_message", {})
        print(f"  [LOG] Tool result stubbed: content_id='{content_id}'")
        print(f"       Stubbed: {stubbed.get('content', '')[:50]}...")
        print(f"       Replacement: {replacement.get('content', '')[:50]}...")

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
            content_id = getattr(r, 'content_id', 'None')
            stub_previous = getattr(r, 'stub_previous', False)
            print(f"       content_id='{content_id}', stub_previous={stub_previous}")

    elif event == "api_response":
        usage = data.get("usage", {})
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = usage.get("total_tokens", 0)
        print(f"  [TOKENS] Context: {prompt:,} tokens | Response: {completion:,} | Cost: {total:,} tokens")

    elif event == "reminder_injected":
        message = data.get("message", "")
        print(f"  [LOG] Reminder injected: {message}")

    elif event == "final_answer":
        answer = data.get("answer", "")
        usage = data.get("usage", {})
        cumulative = data.get("cumulative_usage", {})
        final_context = data.get("final_context_size", 0)

        preview = answer[:100] + "..." if len(answer) > 100 else answer
        print(f"  [LOG] Final answer: {preview}")
        print(f"  [TOKENS] Final context size: {final_context:,} tokens")
        print(f"  [TOKENS] Total spent: {cumulative.get('total_tokens', 0):,} tokens")
        print(f"  [TOKENS]   - Prompt tokens: {cumulative.get('prompt_tokens', 0):,}")
        print(f"  [TOKENS]   - Completion tokens: {cumulative.get('completion_tokens', 0):,}")
        print(f"  [TOKENS]   - API calls: {cumulative.get('request_count', 0)}")

        if final_context > 100000:
            print(f"  WARNING: Context approaching 128K limit!")

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
    ]

    print("\n" + "=" * 70)
    print("AGENT LOOP DEMO WITH STUBBING & TOKEN TRACKING")
    print("=" * 70)
    print("\nNOTE: Stubbing is by content_id with stub_previous.")
    print("  - Weather: content_id = weather_{location}")
    print("  - Time: content_id = current_time")
    print("  - Same content_id with stub_previous=True -> previous result stubbed")
    print("  - content_id=None -> opt-out of stubbing")

    for i, prompt in enumerate(prompts, 1):
        print(f"\n{'=' * 70}")
        print(f"Test #{i}")
        print(f"Prompt: {prompt}")
        print('-' * 70)

        result = agent.run_agent(
            prompt=prompt,
            tools=tools,
            tool_executor=tool_executor,
            logger=logger_callback,
        )

        print('-' * 70)

        # Handle result: FinalAnswer, (signal, history) tuples (termination
        # success / failure), or (error, history) loop failures.
        if isinstance(result, FinalAnswer):
            print(f"Success!\nAnswer: {result.answer}")
            history = result.history
        elif isinstance(result, tuple):
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
                content_id = m.get("_content_id", "None")
                stubbed = m.get("_stubbed", False)
                content_preview = str(m.get("content", ""))[:50]
                status = "STUBBED" if stubbed else "active"
                print(f"     [{status}] content_id='{content_id}': {content_preview}...")
        print('=' * 70)

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
