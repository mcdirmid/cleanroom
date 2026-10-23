# Concrete scenarios for `tool_provider` (interface)

## Scenario 1 — Installing tools and reporting what is installed

Given: an agent session for role alpha in which no tool has been installed yet.

1. The agent asks which tools the session has installed.
   Observed: an empty mapping of tool names to tools.

2. The agent installs the tool `inspect_widget`, described as reading one named widget, whose
   parameters are the required parameter `widget` and the unrequired parameter `unit` with the
   default value `widget`.
   Observed: no tool is called, and the installed tools now map the name `inspect_widget` to a tool
   of that name and description with the parameters `widget` and `unit`.

3. The agent installs the tool `resize_widget`, described as changing the size of one widget, whose
   parameters are the required parameter `widget` and the required parameter `height`.
   Observed: the installed tools map the name `inspect_widget` and the name `resize_widget` to their
   respective tools.

4. The agent asks which tools the session has installed.
   Observed: the mapping holds exactly two entries, keyed by the names `inspect_widget` and
   `resize_widget`.

## Scenario 2 — Executing an installed tool by name

Given: the tool `resize_widget` is installed with the required parameter `widget` and the required
parameter `height`, and the session records the call to that tool.

1. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `height` to the wire integer `30`.
   Observed: the tool `resize_widget` is called once with action parameter bindings mapping its
   parameter `widget` to the actual value for `widget_a` and its parameter `height` to the actual
   value for `30`, and the tool response carries that tool's output and reports that execution did
   not fail.

2. The agent executes the tool `resize_widget` with the argument mappings binding `widget` to the
   wire string `widget_b` and `height` to the wire integer `42`.
   Observed: the tool `resize_widget` is called once more, with the same two actual parameters
   carrying the values for `widget_b` and `42`, and the tool response reports that execution did not
   fail.

## Scenario 3 — Naming a tool that is not installed

Given: the tool `inspect_widget` is installed and the tool `paint_widget` is not installed.

1. The agent executes the tool `paint_widget` with the wired parameter bindings binding `widget` to
   the wire string `widget_a`.
   Observed: the call fails with diagnostic feedback, the response reports that execution failed,
   no tool is called, and the session still holds `inspect_widget` among its installed tools.

2. The agent executes the tool `paint_widget` with no wired parameter bindings.
   Observed: the call fails with diagnostic feedback, and no tool is called.

## Scenario 4 — Supplying a name that the tool does not declare

Given: the tool `inspect_widget` is installed with the required parameter `widget` and the
unrequired parameter `unit`, and the session records the call to that tool.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `colour` to the wire string `red`.
   Observed: the call fails with diagnostic feedback that only declared parameters of the tool can
   be provided, the tool `inspect_widget` is not called, and the response reports that execution
   failed.

2. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `unit` to the wire string `sprocket`.
   Observed: the call does not fail, and the tool `inspect_widget` is called with its parameter
   `widget` bound to the actual value for `widget_a` and its parameter `unit` bound to the actual
   value for `sprocket`.

## Scenario 5 — Omitting a required parameter and taking a default value

Given: the tool `inspect_widget` is installed with the required parameter `widget` and the unrequired
parameter `unit` with the default value `widget`, the required parameter `widget` carries the missing
note `supply widget, the name of the widget to inspect`, and the session records the call to that
tool.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `unit` to
   the wire string `gadget`.
   Observed: the call fails with diagnostic feedback incorporating the missing note `supply widget,
   the name of the widget to inspect`, the feedback states that required parameters of the tool must
   be supplied, and the tool `inspect_widget` is not called.

2. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a`.
   Observed: the default value `widget` is bound for the omitted parameter `unit`, and the tool
   `inspect_widget` is called with its parameter `unit` bound to the actual value for `widget`.

3. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `unit` to the wire string `sprocket`.
   Observed: the tool `inspect_widget` is called with `unit` bound to the actual value for
   `sprocket`, and the default value `widget` is not used.

## Scenario 6 — A parameter type that converts without failing

Given: the tool `inspect_widget` is installed with the required parameter `widget`, whose parameter
type is the identity parameter type, and the session records the call to that tool.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a`.
   Observed: the wire string `widget_a` converts to an identical actual value, the tool
   `inspect_widget` is called with its parameter `widget` bound to that actual value, and the
   response reports that execution did not fail.

2. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire boolean `true`.
   Observed: the conversion does not fail, and the tool `inspect_widget` is called with its
   parameter `widget` bound to the identical actual value for the wire boolean `true`.

## Scenario 7 — A list parameter type and a mapping parameter type

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

2. The agent executes the tool `label_widgets` with the wired parameter bindings binding `widgets`
   to the wire list of the wire string `widget_a` and the wire list of the wire string `widget_b`,
   and binding `labels` to the wire mapping from the wire string `owner` to the wire string `alpha`.
   Observed: the call fails with diagnostic feedback from the element parameter type, and no tool is
   called.

3. The agent executes the tool `label_widgets` with the wired parameter bindings binding `widgets`
   to the wire list of the wire string `widget_a`, and binding `labels` to the wire mapping from the
   wire string `owner` to the wire list of the wire string `alpha`.
   Observed: the call fails with diagnostic feedback from the value parameter type, and no tool is
   called.

## Scenario 8 — A composite parameter type propagating constituent failures

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

2. The agent executes the tool `file_widgets` with the wired parameter bindings binding `entries` to
   the wire mapping from the wire string `cabinet_a` to the wire mapping from the wire string
   `widget_a` to the wire string `widget_b`.
   Observed: the call fails with diagnostic feedback propagated from the constituent parameter
   types, and no tool is called.

## Scenario 9 — Responses that carry a suppression key and a follow-up tool call

Given: the tool `inspect_widget` and the tool `resize_widget` are installed, no suppression key is
declared for the tool `inspect_widget`, and the session records the calls to those tools.

1. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a`.
   Observed: the tool response carries tool output, reports that execution did not fail, and carries
   no suppression key.

2. The agent executes the tool `inspect_widget` again with the wired parameter bindings binding
   `widget` to the wire string `widget_a`.
   Observed: the second tool response also carries no suppression key, so the prior conversation
   response is retained.

3. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_b`.
   Observed: the tool response designates the follow-up tool call of the tool `resize_widget` with
   wired parameter bindings binding `widget` to the wire string `widget_b` and `height` to the wire
   integer `40`, with reasoning text articulating why the next tool is being called.

## Scenario 10 — A tool with no parameters and a session whose tool list is absent

Given: the tool `list_widgets` is installed with no parameters, the tool `inspect_widget` is
installed in the session for role alpha, and no tool has ever been installed in the session for role
beta.

1. The agent executes the tool `list_widgets` with an empty mapping of wired parameter bindings.
   Observed: the tool `list_widgets` is called with empty action parameter bindings and the response
   reports that execution did not fail.

2. The agent asks which tools the session for role beta has installed.
   Observed: an empty mapping of tool names to tools.

3. The agent executes the tool `inspect_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` in the session for role beta.
   Observed: the call fails with diagnostic feedback that no installed tool matches the name, and
   the session for role alpha is unaffected.

## Scenario 11 — Bindings that a caller could not mean

Given: the tool `resize_widget` is installed with the required parameter `widget` and the required
parameter `height`, and the session records the call to that tool.

1. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` twice.
   Observed: the call fails with diagnostic feedback, no tool is called, and the response reports
   that execution failed.

2. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire list of the wire strings `widget_a` and `widget_b` and `height` to the wire integer
   `30`.
   Observed: the call fails with diagnostic feedback from the parameter type of `widget`, and no
   tool is called.

3. The agent executes the tool `resize_widget` with the wired parameter bindings binding `widget`
   to the wire string `widget_a` and `height` to the wire mapping from the wire string `rows` to the
   wire integer `30`.
   Observed: the call fails with diagnostic feedback from the parameter type of `height`, and no
   tool is called.

## Scenario 12 — Converting wire strings with alias manager type

Given: the alias manager type is available in an agent session, and the session's alias manager resolves
the string `widget/notes/draft.md` to a bound file.

1. The caller converts the wire string `widget/notes/draft.md` with the alias manager type.
   Observed: the conversion produces the bound file resolved by the alias manager without failure.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:11:55Z
CHANGE: Author sandbox tool_provider concrete scenarios
-->
