<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:11:55Z
CHANGE: Author sandbox tool_provider_impl concrete scenarios
CODE_HASH: 38176eb9cbcf
-->

# Concrete scenarios for `tool_provider_impl` (implementation)

Scenarios 1 through 11 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 12 through
15 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Installing tools and reporting what is installed

Given: an agent session for role alpha in which no tool has been installed yet.

1. The agent asks which tools the session has installed.
   Observed: an empty mapping of tool names to tools.
   Realized by: the component's own in-memory session registry, which was initialized empty for the
   active session and is written by the installation operation.

2. The agent installs the tool `inspect_widget`, described as reading one named widget, whose
   parameters are the required parameter `widget` and the unrequired parameter `unit` with the
   default value `widget`.
   Observed: no tool is called, and the installed tools now map the name `inspect_widget` to a tool
   of that name and description with the parameters `widget` and `unit`.
   Realized by: the component's own tool installation operation writing the tool into the in-memory
   session registry, keyed by its name.

3. The agent installs the tool `resize_widget`, described as changing the size of one widget, whose
   parameters are the required parameter `widget` and the required parameter `height`.
   Observed: the installed tools map the name `inspect_widget` and the name `resize_widget` to their
   respective tools.
   Realized by: the component's own tool installation operation, adding a second entry beside the
   first in the in-memory session registry.

4. The agent asks which tools the session has installed.
   Observed: the mapping holds exactly two entries, keyed by the names `inspect_widget` and
   `resize_widget`.
   Realized by: the component's own read of the in-memory session registry, which the installation
   operation writes.

### Scenario 2 — Executing an installed tool by name

Given: the tool `resize_widget` is installed with the required parameter `widget` and the required
parameter `height`, and the session records the call to that tool.

1. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `height` to the wire integer `30`.
   Observed: the tool `resize_widget` is called once with action parameter bindings mapping its
   parameter `widget` to the actual value for `widget_a` and its parameter `height` to the actual
   value for `30`, and the tool response carries that tool's output and reports that execution did
   not fail.
   Realized by: the component's own name lookup in the in-memory session registry, its own
   resolution of the parameter specifications declared on the tool, its own invocation of the
   parameter types declared for `widget` and `height`, and its own pass-through of the response
   object the tool returns.

2. The agent executes the tool `resize_widget` with the argument mappings binding `widget` to the
   wire string `widget_b` and `height` to the wire integer `42`.
   Observed: the tool `resize_widget` is called once more, with the same two actual parameters
   carrying the values for `widget_b` and `42`, and the tool response reports that execution did not
   fail.
   Realized by: the component's own argument-mapping entry point, which rewrites the supplied
   mapping into wire parameter bindings and then takes the same resolution path.

### Scenario 3 — Naming a tool that is not installed

Given: the tool `inspect_widget` is installed and the tool `paint_widget` is not installed.

1. The agent executes the tool `paint_widget` with the wired parameter bindings binding `widget` to
   the wire string `widget_a`.
   Observed: the call fails with diagnostic feedback, the response reports that execution failed,
   no tool is called, and the session still holds `inspect_widget` among its installed tools.
   Realized by: the component's own name lookup in the in-memory session registry, which the
   installation operation writes, and its own refusal for a name with no matching entry, leaving the
   registry untouched.

2. The agent executes the tool `paint_widget` with no wired parameter bindings.
   Observed: the call fails with diagnostic feedback, and no tool is called.
   Realized by: the same failed lookup, which precedes any argument resolution.

### Scenario 4 — Supplying a name that the tool does not declare

Given: the tool `inspect_widget` is installed with the required parameter `widget` and the
unrequired parameter `unit`, and the session records the call to that tool.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `colour` to the wire string `red`.
   Observed: the call fails with diagnostic feedback that only declared parameters of the tool can
   be provided, the tool `inspect_widget` is not called, and the response reports that execution
   failed.
   Realized by: the component's own parameter-binding check, which compares every supplied name
   against the parameter specifications declared on the tool and refuses the undeclared name
   `colour`.

2. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `unit` to the wire string `sprocket`.
   Observed: the call does not fail, and the tool `inspect_widget` is called with its parameter
   `widget` bound to the actual value for `widget_a` and its parameter `unit` bound to the actual
   value for `sprocket`.
   Realized by: the same parameter-binding check, now matching every supplied name, followed by the
   parameter types declared for `widget` and `unit`.

### Scenario 5 — Omitting a required parameter and taking a default value

Given: the tool `inspect_widget` is installed with the required parameter `widget` and the
unrequired parameter `unit` with the default value `widget`, the required parameter `widget` carries
the missing note `supply widget, the name of the widget to inspect`, and the session records the
call to that tool.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `unit` to
   the wire string `gadget`.
   Observed: the call fails with diagnostic feedback incorporating the missing note `supply widget,
   the name of the widget to inspect`, the feedback states that required parameters of the tool must
   be supplied, and the tool `inspect_widget` is not called.
   Realized by: the component's own requirement check, which evaluates the missing note of the
   omitted required parameter against the names that were supplied.

2. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a`.
   Observed: the default value `widget` is bound for the omitted parameter `unit`, and the tool
   `inspect_widget` is called with its parameter `unit` bound to the actual value for `widget`.
   Realized by: the component's own default-value binding, which writes the configured default into
   the action parameter bindings before the tool is called, and the identity conversion performed by
   the parameter type of `unit`.

3. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `unit` to the wire string `sprocket`.
   Observed: the tool `inspect_widget` is called with `unit` bound to the actual value for
   `sprocket`, and the default value `widget` is not used.
   Realized by: the component's own default-value binding, which applies only to parameters absent
   from the supplied bindings.

### Scenario 6 — A parameter type that converts without failing

Given: the tool `inspect_widget` is installed with the required parameter `widget`, whose parameter
type is the identity parameter type, and the session records the call to that tool.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a`.
   Observed: the wire string `widget_a` converts to an identical actual value, the tool
   `inspect_widget` is called with its parameter `widget` bound to that actual value, and the
   response reports that execution did not fail.
   Realized by: the component's own identity parameter type, whose conversion returns the wire value
   unchanged and reports no failure.

2. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire boolean `true`.
   Observed: the conversion does not fail, and the tool `inspect_widget` is called with its
   parameter `widget` bound to the identical actual value for the wire boolean `true`.
   Realized by: the same identity conversion, which reports no failure for any wire value.

### Scenario 7 — A list parameter type and a mapping parameter type

Given: the tool `label_widgets` is installed, described as labelling widgets, whose required
parameter `widgets` has a list parameter type whose element parameter type is the identity parameter
type, and whose required parameter `labels` has a mapping parameter type whose key parameter type
and value parameter type are both the identity parameter type.

1. The agent executes the tool `label_widgets` with the wired parameter bindings binding `widgets`
   to the wire list of the wire strings `widget_a` and `widget_b`, and binding `labels` to the wire
   mapping from the wire string `owner` to the wire string `alpha`.
   Observed: the list converts element-wise into an actual list of the actual values for `widget_a`
   and `widget_b`, the mapping converts key-wise and value-wise into an actual mapping from the
   actual value for `owner` to the actual value for `alpha`, and the tool `label_widgets` is called
   with both actual values.
   Realized by: the component's own list parameter type, which converts each element through its
   element parameter type, and its own mapping parameter type, which converts each key and each
   value through its key and value parameter types.

2. The agent executes the tool `label_widgets` with the wired parameter bindings binding `widgets`
   to the wire list of the wire string `widget_a` and the wire list of the wire string `widget_b`,
   and binding `labels` to the wire mapping from the wire string `owner` to the wire string `alpha`.
   Observed: the call fails with diagnostic feedback from the element parameter type, and no tool is
   called.
   Realized by: the component's own list parameter type, which propagates the failure its element
   parameter type reports for the nested list.

3. The agent executes the tool `label_widgets` with the wired parameter bindings binding `widgets`
   to the wire list of the wire string `widget_a`, and binding `labels` to the wire mapping from the
   wire string `owner` to the wire list of the wire string `alpha`.
   Observed: the call fails with diagnostic feedback from the value parameter type, and no tool is
   called.
   Realized by: the component's own mapping parameter type, which propagates the failure its value
   parameter type reports for the nested list.

### Scenario 8 — A composite parameter type propagating constituent failures

Given: the tool `file_widgets` is installed, described as filing widgets, whose required parameter
`entries` has a mapping parameter type whose key parameter type is the identity parameter type and
whose value parameter type is a list parameter type with the identity parameter type as its element
parameter type.

1. The agent executes the tool `file_widgets` with the wired parameter bindings binding `entries` to
   the wire mapping from the wire string `cabinet_a` to the wire list of the wire strings `widget_a`
   and `widget_b`.
   Observed: the mapping converts into an actual mapping from the actual value for `cabinet_a` to an
   actual list of the actual values for `widget_a` and `widget_b`, and the tool `file_widgets` is
   called with it.
   Realized by: the component's own composite parameter type built from a mapping parameter type and
   a list parameter type, each of which converts through the parameter types it was formed from.

2. The agent executes the tool `file_widgets` with the wired parameter bindings binding `entries` to
   the wire mapping from the wire string `cabinet_a` to the wire mapping from the wire string
   `widget_a` to the wire string `widget_b`.
   Observed: the call fails with diagnostic feedback propagated from the constituent parameter
   types, and no tool is called.
   Realized by: the same composite parameter type, which propagates every failure reported by its
   constituents.

### Scenario 9 — Responses that carry a suppression key and a follow-up tool call

Given: the tool `inspect_widget` and the tool `resize_widget` are installed, no suppression key is
declared for the tool `inspect_widget`, and the session records the calls to those tools.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a`.
   Observed: the tool response carries tool output, reports that execution did not fail, and carries
   no suppression key.
   Realized by: the component's own pass-through of the response object the tool returns, which
   leaves the suppression key unset because none was declared.

2. The agent executes the tool `inspect_widget` again with the wired parameter bindings binding
   `widget` to the wire string `widget_a`.
   Observed: the second tool response also carries no suppression key, so the prior conversation
   response is retained.
   Realized by: the same pass-through, which the component performs without inspecting the prior
   conversation.

3. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_b`.
   Observed: the tool response designates the follow-up tool call of the tool `resize_widget` with
   wired parameter bindings binding `widget` to the wire string `widget_b` and `height` to the wire
   integer `40`, with reasoning text articulating why the next tool is being called.
   Realized by: the component's own pass-through of the follow-up tool call the tool attached to its
   response, without resolving its bindings.

### Scenario 10 — A tool with no parameters and a session whose tool list is absent

Given: the tool `list_widgets` is installed with no parameters, the tool `inspect_widget` is
installed in the session for role alpha, and no tool has ever been installed in the session for role
beta.

1. The agent executes the tool `list_widgets` with an empty mapping of wired parameter bindings.
   Observed: the tool `list_widgets` is called with empty action parameter bindings and the response
   reports that execution did not fail.
   Realized by: the component's own resolution path, which finds no parameter specifications to
   check, no defaults to bind, and no requirements to enforce.

2. The agent asks which tools the session for role beta has installed.
   Observed: an empty mapping of tool names to tools.
   Realized by: the component's own in-memory session registry, which holds a separate entry per
   session and remains empty in the session for role beta.

3. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` in the session for role beta.
   Observed: the call fails with diagnostic feedback that no installed tool matches the name, and
   the session for role alpha is unaffected.
   Realized by: the component's own session-scoped registry lookup, which reads only the registry of
   the session that made the call.

### Scenario 11 — Bindings that a caller could not mean

Given: the tool `resize_widget` is installed with the required parameter `widget` and the required
parameter `height`, and the session records the call to that tool.

1. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` twice.
   Observed: the call fails with diagnostic feedback, no tool is called, and the response reports
   that execution failed.
   Realized by: the component's own parameter-binding check, which refuses a binding mapping that
   names a parameter more than once.

2. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire list of the wire strings `widget_a` and `widget_b` and `height` to the wire integer
   `30`.
   Observed: the call fails with diagnostic feedback from the parameter type of `widget`, and no
   tool is called.
   Realized by: the parameter type declared for `widget`, whose conversion of a wire list reports a
   failure that the component forwards as diagnostic feedback.

3. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `height` to the wire mapping from the wire string `rows` to the
   wire integer `30`.
   Observed: the call fails with diagnostic feedback from the parameter type of `height`, and no
   tool is called.
   Realized by: the parameter type declared for `height`, whose conversion of a wire mapping reports
   a failure that the component forwards as diagnostic feedback.

## Implementation-only

### Scenario 12 — Installing a tool name that is already installed

Given: the tool `inspect_widget` is installed, described as reading one named widget, and the
session records the call to that tool.

1. The agent installs the tool `inspect_widget` again, described as reading one named widget
   quickly, whose parameters are the required parameter `widget`.
   Observed: the installed tools hold one entry under the name `inspect_widget`, and that entry is
   the tool just installed.
   Realized by: the component's own tool installation operation, which overwrites the registry entry
   under an existing name.

2. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a`.
   Observed: the tool just installed is called, and the session holds one tool name rather than two.
   Realized by: the same name lookup, which resolves to the entry written most recently.

### Scenario 13 — The order in which argument resolution reports failures

Given: the tool `paint_widget` is not installed, the tool `inspect_widget` is installed with the
required parameter `widget`, and the session records the call to that tool.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `colour` to the wire string `red`.
   Observed: the call fails with the diagnostic feedback about an undeclared parameter, and not with
   the diagnostic feedback about the missing required parameter `widget`.
   Realized by: the component's own resolution order, which checks the supplied names against the
   declared parameters before it evaluates requirements.

2. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `colour`
   to the wire string `red`.
   Observed: the call fails with the diagnostic feedback about an undeclared parameter, and not with
   the diagnostic feedback about the missing required parameter `widget`.
   Realized by: the same resolution order, which the undeclared-name check precedes.

3. The agent executes the tool `paint_widget` with the wired parameter bindings binding `colour` to
   the wire string `red`.
   Observed: the call fails with the diagnostic feedback that no installed tool matches the name,
   and not with the feedback about an undeclared parameter.
   Realized by: the same resolution order, which matches the tool name before it inspects any
   supplied parameter name.

### Scenario 14 — Reinstalling a tool whose unrequired parameter carries a default

Given: the tool `inspect_widget` is installed with the required parameter `widget` and the
unrequired parameter `unit` whose default value is the wire string `widget`.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `unit` to the wire string `gadget`.
   Observed: the tool is called with `unit` bound to the actual value for `gadget`, and the
   configured default is not applied over it.
   Realized by: the component's own default-value binding, which is consulted only when a parameter
   has no supplied binding.

2. The agent installs the tool `inspect_widget` again with the required parameter `widget` and no
   parameter named `unit`, and then executes it with the wired parameter bindings binding `widget`
   to the wire string `widget_a`.
   Observed: the tool is called with the parameters `widget` alone, and no default for `unit` is
   bound.
   Realized by: the component's own tool installation operation, which replaces the registry entry,
   and the subsequent resolution of the parameters declared on the replacement.

### Scenario 15 — A wire value outside the wire value kinds

Given: the tool `resize_widget` is installed with the required parameter `widget` and the required
parameter `height`, and the session records the call to that tool.

1. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget` to
   the wire string `widget_a` and `height` to the value `2026-01-02T03:04:05Z`, which is not one of
   the wire value kinds.
   Observed: the call fails with diagnostic feedback, and no tool is called.
   Realized by: the component's own conversion path, which rejects a binding whose wire value is not
   one of the wire value kinds, and its own refusal naming the offending parameter.

2. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget` to
   the wire string `widget_a` and supplying no binding for `height`.
   Observed: the call fails with the diagnostic feedback about the missing required parameter
   `height`, and no tool is called.
   Realized by: the component's own requirement check, which treats an absent binding as an
   unsupplied argument.
