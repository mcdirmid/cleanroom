# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:02Z
# LAST_CHANGED: 2026-10-11T03:37:04Z
# CHANGE: Ground driver coordination and complete the run contract set
# CODE_HASH: 645a45c2256f
# SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
# --- END CLEANROOM METADATA ---

"""OpenAI driver implementation low-level specification."""

from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import loop_driver
import agent_config
import loop_conversation
import loop_guard
import openai_config
import runner_logger
import tool_provider


@singleton_type("agent_session")
class LoopDriver(
    loop_driver.LoopDriver, InTier[AgentSessionTier]
):
    """Realizes language model completion requests, tool dispatch, output continuation, and termination handling.

    GROUNDING:
    - Realizes loop_driver.LoopDriver.run as the loop_driver_service knowledge provision by
      coordinating interaction turns across loop_conversation.Conversation,
      tool_provider.ToolManager, loop_guard.LoopGuard, openai_config.OpenAIConfig,
      agent_config.AgentConfig, and runner_logger.RunnerLogger, and produces the
      loop_driver.LoopOutcome carrying the terminating tool_provider.ToolResponse and the final
      loop_conversation.ModelRequest.
    - Transmits completion requests over the openai_ext wire protocol for the openai_wire_operations
      knowledge provision, binding openai_config.OpenAIConfig.model_name,
      openai_config.OpenAIConfig.base_url, openai_config.OpenAIConfig.api_key,
      openai_config.OpenAIConfig.timeout, openai_config.OpenAIConfig.temperature, and
      openai_config.OpenAIConfig.max_tokens into the request payload, and reads the conversation
      history through loop_conversation.Conversation.get_model_request.
    - Orders the tools exposed by tool_provider.ToolManager.installed_tools by
      tool_provider.Tool.name and the parameters of tool_provider.Tool.parameters by declared
      sequence, then dispatches model-invoked calls through tool_provider.ToolManager.execute_tool
      and records each tool_provider.ToolResponse against its originating call identifier through
      loop_conversation.Conversation.append_tool_response.
    - Repairs truncated generations through the json_ext json_operations knowledge provision by
      rewriting unclosed tool arguments into valid JSON and by replacing partial replace file
      content payloads with an indented NotImplementedError sentinel whose incrementing session
      truncation identifier is held in internal backing state, then persists the repair by
      re-executing it through tool_provider.ToolManager.execute_tool.
    - Tracks consecutive tool invocations through loop_guard.LoopGuard.evaluate and clears the
      recorded repetition through loop_guard.LoopGuard.reset when an execution modifies workspace
      files or advances the guide step, grounding the loop_guard_service knowledge provision.
    - Streams turn requests, completions, and tool results as runner_logger.RunnerLogEvent records
      through runner_logger.RunnerLogger.consume, grounding the runner_logging_service knowledge
      provision.
    - Executes chained follow-up calls gated by agent_config.AgentConfig.inject_followups by
      dispatching the designated tool through tool_provider.ToolManager.execute_tool and appending
      the synthetic assistant invocation and its response through
      loop_conversation.Conversation.append_message.
    - Counts interaction turns in internal backing state against
      agent_config.AgentConfig.conversation_limit, grounding the agent_configuration_parameters
      knowledge provision.
    """

    @operation
    @override
    def run(self) -> loop_driver.LoopOutcome:
        """Drives iterative turns using OpenAI completion requests.

        Returns:
            The final loop outcome carrying the terminating tool response and the final conversation state.

        GROUNDING:
        - Coordinates each interaction turn over loop_conversation.Conversation.get_model_request,
          tool_provider.ToolManager.installed_tools, loop_guard.LoopGuard.evaluate,
          openai_config.OpenAIConfig.model_name, agent_config.AgentConfig.conversation_limit, and
          runner_logger.RunnerLogger.consume.
        - Transmits the assembled payload over the openai_ext wire protocol, binding
          openai_config.OpenAIConfig.base_url, openai_config.OpenAIConfig.api_key,
          openai_config.OpenAIConfig.timeout, openai_config.OpenAIConfig.temperature, and
          openai_config.OpenAIConfig.max_tokens.
        - Dispatches each ordered tool through tool_provider.ToolManager.execute_tool and records
          the resulting tool_provider.ToolResponse through
          loop_conversation.Conversation.append_tool_response using the originating tool call
          identifier.
        - Repairs truncated replace file content payloads through the json_ext json_operations
          knowledge provision, mutates the incrementing session truncation identifier held in
          internal backing state, and clears repetition through loop_guard.LoopGuard.reset whenever
          an execution modifies workspace files or advances the guide step.

        POSTCONDITIONS:
        - MUST transmit a completion request following OpenAI chat completion conventions.
        - MUST bind model parameters from the OpenAI configuration into the transmitted request.
        - MUST order tools deterministically by tool name.
        - MUST order tool parameters deterministically by parameter sequence.
        - MUST correlate tool results with model invocations by their tool call identifiers.
        - WHEN a model response is truncated at the generation limit, MUST recover truncated tool
          invocations by repairing unclosed arguments into valid JSON.
        - WHEN a replace file content invocation provides a target file, target content, and partial
          replacement content, MUST delete a trailing incomplete line lacking a terminating newline
          and replace it with a sentinel raising a non implemented error carrying an incrementing
          session truncation identifier matching indentation.
        - WHEN the last line of partial replacement content is complete, MUST append the sentinel on
          the next line matching indentation.
        - WHEN a truncated replace file content invocation is repaired, MUST execute the repaired
          tool to persist the partial modifications.
        - WHEN a truncated replace file content invocation is repaired, MUST return an actionable
          notice directing the model to resume implementation targeting the sentinel.
        - WHEN the truncated invocation is any other tool, MUST terminate it by appending a tool
          failure response with the tool suppression key.
        - WHEN a truncated tool invocation is handled, MUST resume generation with a continuation
          turn.
        - WHEN a model completion response fails with an incomplete tool call error, MUST append an
          actionable recovery notice directing smaller edits.
        - WHEN handling an incomplete tool call error, MUST resume generation with a continuation
          turn.
        - WHEN repeated consecutive truncation failures occur, MUST halt execution with an
          unexpected failure.
        - MUST log turn requests, completions, and tool results to the runner logger.
        - MUST format compact log summaries carrying turn identifiers, token size, percentage of
          cached tokens, tool names, arguments, and execution status without inlining file content.
        - WHEN corrective reminders are present, MUST include them in the logged transcript.
        - WHEN the loop guard produces a loop failure, MUST halt execution with an unexpected
          failure carrying the explanation.
        - WHEN the loop guard produces a loop reminder, MUST append the reminder to the conversation.
        - WHEN tool execution modifies workspace files or advances the guide step, MUST clear
          repetition tracking through the loop guard.
        - WHEN tool execution produces a non-terminating failure response, MUST append failure
          feedback to the conversation.
        - WHEN tool execution produces a terminating failure response, MUST halt execution with an
          unexpected failure.
        - WHEN tool execution produces a successful termination response, MUST return a successful
          loop outcome.
        - WHEN the agent configuration directs follow-up injection and a response specifies a
          follow-up tool call, MUST execute the designated tool.
        - WHEN a designated follow-up tool is executed, MUST append a synthetic assistant invocation
          carrying the reasoning text as prior thought.
        - WHEN a follow-up tool response is produced, MUST append it to the conversation immediately
          following the originating response.
        - WHEN a model response produces no tool executions, MUST append a prompt reminding that
          progress requires invoking tools.
        - WHEN interaction turns reach the conversation limit from the agent configuration, MUST halt
          execution with an unexpected failure indicating that the conversation limit was reached.
        """
        ...
