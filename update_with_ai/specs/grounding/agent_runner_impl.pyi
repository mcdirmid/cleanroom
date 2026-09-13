from framework import operation, override, singleton_type
import agent_conversation_history
import agent_loop_guard
import agent_runner
import model_config
import openai_ext
import runner_logger
import tool_provider

@singleton_type('agent_session')
class AgentRunner(agent_runner.AgentRunner):
    """
PURPOSE:
Implements agent runner with model completions and continuation turns

GROUNDING_ARGUMENT:
- As an agent_session singleton, AgentRunner accesses collaborator singletons in the same lifecycle tier (agent_conversation_history.ConversationHistory, agent_loop_guard.LoopGuard, tool_provider.ToolManager) and in the more general system lifecycle tier (model_config.ModelConfig, runner_logger.RunnerLogger), all of which are imported.
"""

    @operation
    @override
    def run(self) -> agent_runner.AgentOutcome:
        """
PURPOSE:
Drives turns using completion requests and tool manager execution

FRESH_REQUIREMENTS:
- When driving a turn, the agent runner transmits a completion request following OpenAI chat completion conventions, using the model name, base url, api key, timeout, temperature, and max tokens bound when configured from model config, tools ordered deterministically by tool name with parameters ordered deterministically by parameter name, and correlates tool results with model invocations according to OpenAI tool calling conventions.
- When a model response is truncated at the generation limit, the agent runner resumes generation with a continuation turn.
- The agent runner logs log events for requests, completions, and tool results to the runner logger, formatting compact summaries with turn identifiers, prefix reuse measurements comparing current wire payloads against previous request payloads with divergence diagnostics, tool names and arguments or text previews, and execution outcomes, including corrective reminders in tool result transcripts when present.
- Before executing each tool call, the agent runner records the tool execution in the loop guard, injecting a loop reminder into the conversation history when a reminder is produced, or concluding the run with an unexpected failure when a loop failure is produced.
- Productive tool executions that modify workspace files or advance the guide step clear repetition tracking in the loop guard.
- When tool execution produces a non-terminating failure response, the failure feedback is appended to the conversation history and the run continues.
- When configured by model configuration to inject followups, a tool response specifying a follow-up tool call prompts execution of the designated tool, appending a synthetic assistant invocation carrying the follow-up tool call's reasoning text as prior thought preceding the requested tool execution and the resulting follow-up response to the conversation history immediately following the originating response.
- When a model response produces no tool executions, the agent runner appends a prompt to the conversation history reminding that progress and conclusion require invoking tools, and continues the turn loop.
- When tool execution produces a terminating response, the agent runner concludes the run and returns an agent outcome, or halts with an unexpected failure if the response indicates terminating failure.
- When turns reach the conversation limit from model config, the agent runner halts with an unexpected failure.

INHERITED_REQUIREMENTS:
- [AgentRunner] The agent runner drives turns by sending model requests to a language model and executing requested tools.
- [AgentRunner] The agent runner appends model responses and correlates tool responses with tool call identifiers in conversation history.
- [AgentRunner] The agent runner can dispatch follow-up tool calls specified by tool responses, recording the follow-up execution in the conversation history.
- [AgentRunner] The agent runner records log events for interaction turns, tool executions, and turn outcomes to the runner logger.
- [AgentRunner] The agent runner evaluates tool executions with the loop guard, injecting reminders or halting with an unexpected failure on runaway repetition.
- [AgentRunner] When a model response contains no tool executions, the agent runner injects a tool reminder into the conversation history and continues the turn loop.
- [AgentRunner] When tool execution produces a termination outcome, the agent runner concludes and returns an agent outcome, or halts with an unexpected failure if the termination indicates a failing outcome.
- [AgentRunner] When the conversation limit from model config is exceeded, the agent runner halts with an unexpected failure.

GROUNDING_ARGUMENT:
- Accesses configuration properties including inject_followups from model_config.ModelConfig (system tier) to invoke openai_ext with non-zero temperature, logs telemetry event summaries, prefix reuse measurements, and transcripts via runner_logger.RunnerLogger (system tier), drives message state and appends reminder prompts or synthetic follow-up invocations through agent_conversation_history.ConversationHistory (session tier), executes tools and follow-up tool calls through tool_provider.ToolManager (session tier), and evaluates tool calls and clears repetition tracking upon productive progress via agent_loop_guard.LoopGuard (session tier), assuming collaborator requirements hold to produce an AgentOutcome.
"""
        ...
