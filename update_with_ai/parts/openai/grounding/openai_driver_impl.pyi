from framework import operation, override, singleton_type
import agent_config
import loop_conversation
import loop_driver
import loop_guard
import openai_config
import openai_ext
import runner_logger
import tool_provider

@singleton_type('agent_session')
class LoopDriver(loop_driver.LoopDriver):
    """Implements loop driver with model completions and continuation turns.

    GROUNDING_ARGUMENT:
    - grounded_by: loop_conversation.Conversation, loop_guard.LoopGuard, tool_provider.ToolManager, openai_config.OpenaiConfig, agent_config.AgentConfig, runner_logger.RunnerLogger
    """

    @operation
    @override
    def run(self) -> loop_driver.LoopOutcome:
        """
        REQUIREMENTS:
        - When driving a turn, the loop driver transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from openai config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter sequence, and correlates tool results with model invocations according to OpenAI tool calling conventions.
        - When a model response is truncated at the generation limit, the loop driver recovers truncated tool invocations by repairing unclosed arguments into valid JSON: when a replace file content invocation provides a target file, target content, and partial replacement content, any trailing incomplete line without a terminating newline is deleted and replaced with a raise NotImplementedError sentinel carrying an incrementing session truncation identifier matching the indentation of the deleted line, or if the last line is complete the sentinel is appended on the next line matching the last line's indentation, executing the tool to persist partial modifications and returning an actionable notice directing the model to resume implementation targeting the sentinel; otherwise the loop driver terminates the truncated tool invocation by appending a tool failure response with the tool's suppression key, and resumes generation with a continuation turn.
        - The loop driver logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, conversation token size rounded to the nearest thousand tokens and percentage of tokens cached on the last turn from model response usage fields, tool names and arguments or text previews, and tool execution status stating the file read or written and the timestamp without inlining file content, including corrective reminders in tool result transcripts when present.
        - Evaluating a tool invocation with the loop guard records the tool execution in the loop guard, injecting a loop reminder into the conversation when a reminder is produced, or concluding the run with an unexpected failure when a loop failure is produced.
        - Productive tool executions that modify workspace files or advance the guide step clear repetition tracking in the loop guard.
        - When tool execution produces a non-terminating failure response, the failure feedback is appended to the conversation and the run continues.
        - When configured by agent configuration to inject followups, a tool response specifying a follow-up tool call prompts execution of the designated tool, appending a synthetic assistant invocation carrying the follow-up tool call's reasoning text as prior thought preceding the requested tool execution and the resulting follow-up response to the conversation immediately following the originating response.
        - When a model response produces no tool executions, the loop driver appends a prompt to the conversation reminding that progress and conclusion require invoking tools, and continues the turn loop.
        - When tool execution produces a terminating response, the loop driver concludes the run and returns a loop outcome, or halts with an unexpected failure if the response indicates terminating failure.
        - When turns reach the conversation limit from agent config, the loop driver halts with an unexpected failure.

        GROUNDING_PROVISIONS:
        - action("run", loop_driver.LoopOutcome): Drives turns using completion requests and tool manager execution.

        GROUNDING_ARGUMENT:
        - action("run", Self) :- action("get_model_request", loop_conversation.Conversation), action("execute_tool", tool_provider.ToolManager), action("consume_log_event", runner_logger.RunnerLogger), action("record_tool_execution", loop_guard.LoopGuard).
        """
        ...

