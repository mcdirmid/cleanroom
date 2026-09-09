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
- The agent runner transmits completion requests using model name, base url, api key, and timeout from model config with openai_ext.
- When a model response is truncated at the generation limit, the agent runner resumes generation with a continuation turn.
- The agent runner logs log events for requests, completions, and tool results to the runner logger.
- When tool execution produces a non-terminating failure response, the failure feedback is appended to the conversation history and the run continues.
- When tool execution produces a terminating response, the agent runner concludes the run and returns an agent outcome.
- When turns reach the conversation limit from model config, the agent runner concludes with a failure outcome.

INHERITED_REQUIREMENTS:
- [AgentRunner] The agent runner drives turns by sending model requests to a language model and executing requested tools.
- [AgentRunner] The agent runner appends model responses and correlates tool responses with tool call identifiers in conversation history.
- [AgentRunner] The agent runner records log events for model requests, responses, and tool executions to the runner logger.
- [AgentRunner] The agent runner evaluates tool executions with the loop guard, injecting reminders or terminating on failure.
- [AgentRunner] When tool execution produces a termination outcome, the agent runner concludes and returns an agent outcome.
- [AgentRunner] When the conversation limit from model config is exceeded, the agent runner concludes with a failure outcome.

GROUNDING_ARGUMENT:
- Accesses configuration properties from model_config.ModelConfig (system tier) to invoke openai_ext, logs telemetry events via runner_logger.RunnerLogger (system tier), drives message state through agent_conversation_history.ConversationHistory (session tier), executes tools through tool_provider.ToolManager (session tier), and enforces execution guards via agent_loop_guard.LoopGuard (session tier), assuming collaborator requirements hold to produce an AgentOutcome.
"""
        ...
