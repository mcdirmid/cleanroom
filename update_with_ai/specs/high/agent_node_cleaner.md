# agent_node_cleaner

imports: dag_storage, dag_node_cleaner, agent_runner, sandbox, conversation_history, build_graph_storage, runner_logger
types from dag_storage: node, pending message
types from dag_node_cleaner: node cleaner, change message, feedback message
types from agent_runner: agent runner, agent outcome
types from sandbox: sandbox, sandbox factory, sandbox configuration, startup interaction
types from conversation_history: conversation history, conversation history factory
types from build_graph_storage: build graph storage, node definition, task prompt
types from runner_logger: runner logger

## Purpose

Cleans an individual workspace node by driving an isolated agent run within a hermetic sandbox.

Executing node-level agent tasks requires orchestrating the sandbox environment, prompt assembly, and conversation lifecycle for that specific node. Agent node cleaner constructs the node sandbox, initializes the conversation with the node prompt, startup interactions, and pending messages, and drives the agent runner. When execution concludes, it translates the final agent outcome into downstream change messages or upstream feedback messages.

## Types

- An *agent node cleaner* is a *node cleaner* that cleans a *node* by executing an *agent runner* within a *sandbox*

## Behavior

- An *agent node cleaner* retrieves the *node definition*, *task prompt*, and *sandbox configuration* for a dirty *node* from a *build graph storage*.
- Creating a *sandbox* through a *sandbox factory* yields a *sandbox* configured from the retrieved *sandbox configuration*.
- Creating a *conversation history* through a *conversation history factory* yields a *conversation history*.
- An *agent node cleaner* cleans a dirty *node* by creating a *sandbox* and a *conversation history* and executing an *agent runner* with a *runner logger*.
- An *agent node cleaner* initializes the agent conversation by seeding a *conversation history* with the retrieved *task prompt*, the *startup interaction* from the *sandbox* formatted as synthetic tool call and tool result pairs, and incoming *pending messages*.
- An *agent node cleaner* produces *change messages* when workspace file modifications occur and task verification passes.
- An *agent node cleaner* produces *feedback messages* addressed to dependency *nodes* when blame is signaled.
- An *agent node cleaner* produces no messages when a task without modifications succeeds with no pending feedback.
