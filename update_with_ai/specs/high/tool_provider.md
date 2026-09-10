# tool_provider interface component

## Purpose

The tool_provider interface component enables agents to safely interact with environment capabilities through structured invocation boundaries and actionable outcome feedback.

Autonomous agent loops risk unpredictable deviations when environment actions are unconstrained or when failures produce uninformative errors. Unstructured text interfaces force fragile parsing, whereas rigid crash behaviors prevent autonomous recovery. The tool_provider interface component establishes an extensible contract between the agent orchestration layer and concrete domain tooling, allowing external capabilities to be exposed hermetically while giving agents the structured feedback necessary to self-correct during multi-turn interactions.

**Out of scope:** The tool_provider interface component does not implement concrete domain tools, parse model output streams, or govern the agent turn loop; these are handled by other components.

## Types and Behavior

A *parameter converter* is a polymorphic service that has an *actual type*, a primitive *wire type* (limited to *string*, *integer*, or *boolean*), and can *convert* a wire type value to produce a value of that actual type. An actual type is meta type: its values are references to data types, not the values of those data types.

An *identity parameter converter* is a polymorphic parameter converter that works for parameters where the actual and wire types are the same, wrapping string, integer, or boolean. There are three identity parameter converters, one for each wire type: a *string parameter converter*, an *integer parameter converter*, and a *boolean parameter converter*. Converting a wire type value with an identity parameter converter produces that value directly as its actual value.

A *tool* is a polymorphic service implemented by a component to define an executable action. A tool has a *name* (used to identify the tool), a *description* (which informs the model why and when to use the tool), and *parameters*. A *parameter* describes an input accepted by a tool, having a *name* and a *description* (guiding how arguments are supplied), a *parameter converter*, and can be *required* to indicate that an argument must be supplied for tool execution. It is assumed that all parameters of a tool have unique names.

A tool can be *executed* directly with a set of *actual parameter bindings*, which map parameters to resolved values of their actual types. Executing a tool produces a *response* communicating:

- Whether tool execution *failed*.

- Whether to communicate that the agent session should *terminate*.

- Textual *content* that includes underlying tool execution output. When tool execution fails, the content should include error and diagnostic messages along with guidance on how to execute the tool correctly.

- A textual *reminder* advising the agent on future actions and constraints when guidance is provided.

- If a previous conversation response content should be superceded by this execution, a textual *suppression key* identifying that response.

- If there is a known tool that the agent should always call after this tool execution, a *follow-up tool call* specifying a tool name and wire parameter bindings of that tool.

Direct tool execution with actual parameter bindings is primarily used by components when software needs to invoke an action directly (such as executing a read tool to inject startup context).

The *tool manager* is an agent session service that maintains tools for an agent session. Tools can be *installed* so they are available during the session, and it is assumed that all installed tools have unique names. At the direction of a model during an agent turn, the tool manager *executes* tools by name with *wire parameter bindings* (mapping parameter names to values of their wire types), that, if mappings are successfully resolved, produces the same response as executing the tool directly. The tool manager also exposes *installed tools* to inform the model of what tools can be executed.
