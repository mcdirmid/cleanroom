# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-11T03:21:35Z
# CHANGE: Canonicalize change timestamps, split run failure clauses, and fix LoopDriver.run grounding
# CODE_HASH: d1385fd4b028
# SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
# --- END CLEANROOM METADATA ---

"""Loop node cleaner implementation low-level specification."""

from typing import Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import dag_storage
import loop_node_cleaner
import agent_node_config
import agent_storage
import loop_conversation
import loop_driver
import runner_logger
import sandbox


@singleton_type("system")
class NodeCleaner(loop_node_cleaner.NodeCleaner, InTier[SystemTier]):
    """Realizes node clean execution, session seeding, and message dispatch.

    GROUNDING:
    - Binds abstract node cleaning directives to agent session phases by driving agent turns
      through the LoopDriver collaborator and translating the returned LoopOutcome into in-band
      DagStorage state mutations.
    - Holds no internal backing collections of its own, accessing the agent session tier peers
      RoleConfig, Conversation, and LoopDriver and the system tier peers DagStorage, AgentStorage,
      Sandbox, and RunnerLogger as flat collaborators.
    - Establishes every session phase across those peers: RoleConfig.set_role presents the role of
      the dirty nodes, Conversation.initialize seeds the conversation history with the initial task
      messages that direct the agent to call the get work tool, and LoopDriver.run drives the
      iterative agent turns and returns the LoopOutcome carrying the termination response and the
      final conversation state.
    - Reports unexpected execution failures through RunnerLogger.consume, retries LoopDriver.run
      exactly once, and propagates the failure when the retried session phase fails.
    - Resolves dirty nodes from the LoopOutcome termination response, consulting
      Sandbox.has_modifications for workspace file modification status and
      NodeConfig.blame_targets_by_node for configured blame targets, then mutates clean status and
      feedback messages in the DagStorage collaborator.
    - Marks nodes clean through DagStorage.mark_node_clean, passing a change description when the
      outcome signals advancement with workspace file modifications and omitting it when no
      workspace files were modified so the last changed timestamp is preserved.
    - Routes blame through DagStorage.add_feedback_message, recording a FeedbackMessage addressed
      to the feedback dependency DagNode owning the blamed file, and leaves nodes dirty when the
      blamed file matches no configured blame target.
    - Short-circuits promptless batches before any session phase, reading AgentStorage.get_task_prompt
      together with the incoming DagStorage.get_messages to decide whether the node is marked clean
      with a change summary or without changes.
    """

    @operation
    @override
    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool:
        """Cleans dirty nodes within an agent session phase.

        Args:
            nodes: The sequence of dirty nodes sharing a role to clean.

        Returns:
            True if processing should continue, or False if an unhandleable failure occurred.

        GROUNDING:
        - Establishes the agent session phase by calling RoleConfig.set_role with the role shared by
          the supplied dirty nodes, then Conversation.initialize with the seeded initial messages
          that instruct the agent to call the get work tool.
        - Drives the phase with LoopDriver.run, reading the returned LoopOutcome.response
          termination signal and LoopOutcome.conversation final conversation state.
        - Wraps the phase in a single retry: on an unexpected execution failure it consumes a
          RunnerLogger event through RunnerLogger.consume, reruns LoopDriver.run once, and
          propagates the failure when the retried run fails again.
        - Evaluates the termination signal for successful advancement by reading
          Sandbox.has_modifications, then calls DagStorage.mark_node_clean with the change summary
          for modified workspaces and without a change summary for unmodified workspaces.
        - Resolves a blamed file to its owning node through NodeConfig.blame_targets_by_node and
          records the resulting FeedbackMessage with its target set to that feedback dependency node
          through DagStorage.add_feedback_message.
        - Leaves the supplied nodes dirty without producing propagating messages when the
          termination signal reports a run failure, and signals that processing cannot continue.
        - Resolves promptless batches before any session phase is established, using
          AgentStorage.get_task_prompt to detect the missing task prompt and the incoming
          DagStorage.get_messages to decide whether to mark the nodes clean with a change summary or
          without changes.
        - Marks cleaned nodes clean in graph storage through DagStorage.mark_node_clean and delivers
          resulting feedback messages strictly to their addressed feedback dependency node, never to
          non-feedback dependencies.

        POSTCONDITIONS:
        - MUST clean dirty nodes within an agent session phase.
        - MUST present the role of the dirty nodes to session services through the role config.
        - MUST initialize conversation history with instructions directing the agent to call the get work tool.
        - MUST drive the agent turns of the session phase.
        - MUST log unexpected execution failures to the runner logger.
        - WHEN an unexpected execution failure occurs, MUST retry the session phase once.
        - WHEN the retried session phase fails, MUST propagate the unexpected execution failure.
        - MUST resolve dirty nodes by evaluating the loop driver outcome.
        - WHEN the outcome signals successful advancement with workspace file modifications, MUST mark the nodes clean in graph storage with the change summary.
        - WHEN no workspace files were modified, MUST mark the nodes clean without advancing change timestamps.
        - WHEN the outcome signals blame attributed to a configured blame target, MUST produce feedback messages addressed strictly to the declared feedback dependency node owning the blamed file.
        - WHEN the blamed file matches no configured blame target, MUST produce no feedback message and leave the nodes dirty.
        - WHEN the outcome signals run failure, MUST produce no propagating messages.
        - WHEN the outcome signals run failure, MUST leave the nodes dirty.
        - WHEN the outcome signals run failure, MUST signal that processing cannot continue.
        - WHEN dirty nodes define no task prompt, MUST resolve the nodes without establishing an agent session phase.
        - WHEN dirty nodes define no task prompt and incoming messages indicate upstream changes, MUST mark the nodes clean with a change summary.
        - WHEN dirty nodes define no task prompt and incoming messages indicate no upstream changes, MUST mark the nodes clean without changes.
        - MUST mark cleaned nodes clean in graph storage.
        - MUST deliver resulting feedback messages strictly to their addressed feedback dependency node.
        - MUST NOT deliver feedback messages to non-feedback dependencies.
        """
        ...
