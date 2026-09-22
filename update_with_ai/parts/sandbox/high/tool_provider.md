# tool_provider interface component

## Purpose

The tool_provider interface component enables agents to safely interact with environment capabilities through structured invocation boundaries and actionable outcome feedback.

Autonomous agent loops risk unpredictable deviations when environment actions are unconstrained or when failures produce uninformative errors. Unstructured text interfaces force fragile parsing, whereas rigid crash behaviors prevent autonomous recovery. The tool_provider interface component establishes an extensible contract between the agent orchestration layer and concrete domain tooling, allowing external capabilities to be exposed hermetically while giving agents the structured feedback necessary to self-correct during multi-turn interactions.

**Out of scope:** The tool_provider interface component does not implement concrete domain tools, parse model output streams, or govern the agent turn loop; these are handled by other components.

## Types and Behavior

A *parameter type* is a polymorphic service that has an *actual type*, a primitive *wire type* (limited to *string*, *integer*, *boolean*, *float*, *list*, or *dictionary*), and can *convert* a wire type value to produce a value of that actual type. An actual type is a meta type: its values are references to data types, not the values of those data types.

An *identity parameter type* is a parameter type that works for parameters where the actual and wire types are the same target type. Converting a wire type value with an identity parameter type produces that value directly as its actual value.

A *list parameter type* is a parameter type that converts a wire type list to an actual type list, having an *item parameter type* that converts individual elements. Converting a wire type list with a list parameter type converts each element with its item parameter type.

A *dictionary parameter type* is a parameter type that converts a wire type dictionary to an actual type dictionary, having a *key parameter type* that converts dictionary keys and a *value parameter type* that converts dictionary values. Converting a wire type dictionary with a dictionary parameter type converts each key with its key parameter type and each value with its value parameter type.

A *tool* is a polymorphic service implemented by a component to define an executable action. A tool has a *name* (used to identify the tool), a *description* (which informs the model why and when to use the tool), and *parameters*.

A *parameter* describes an input accepted by a tool, identified by a *name* and a *description* guiding how arguments are supplied. It is assumed that all parameters of a tool have unique names.

Parameters define argument validation and binding rules for tool execution. A parameter specifies:

- A parameter type converting wire arguments to actual types.

- A *default value* bound during tool execution when an argument is omitted for a parameter that is not required.

- A *required* status indicating that an argument must be supplied for tool execution.

- A *missing message* function producing diagnostic text from the set of supplied parameter names when an argument is omitted for a required parameter.

A tool can be *executed* directly with a set of *actual parameter bindings*, which map parameters to resolved values of their actual types. Executing a tool produces a *response* communicating:

- Whether tool execution *failed*.

- Whether to communicate that the agent session should *terminate*.

- Textual *content* that includes underlying tool execution output. When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

- A textual *reminder* advising the agent on future actions and constraints declaratively and impersonally without second-person pronouns when guidance is provided.

- If a previous conversation response content should be superceded by this execution, a textual *suppression key* identifying that response.

- If there is a known tool that the agent should always call after this tool execution, a *follow-up tool call* specifying a tool name, wire parameter bindings of that tool, and *reasoning text* representing injected model thought in the first-person perspective on why the follow-up tool is being called.

The *tool manager* is an agent session service that maintains tools for an agent session.

The tool manager:

- *Installs tools* for the agent session, assuming all installed tools have unique names.

- Exposes *installed tools* available for execution.

- *Executes* tools by name with *wire parameter bindings* mapping parameter names to wire type values, producing the tool response upon resolving parameter conversions.

- *Executes tools with arguments* by name with raw argument mappings from parameter names to arguments, producing the tool response upon resolving parameter conversions.

- *Creates tool callables* producing executable callable routines configured with parameter signatures and documentation for external server registration, returning the tool response content combined with reminders when present.
