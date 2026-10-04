# Planning Canvas Specification Architecture

## 1. Overview & Architectural Purpose

In the Cleanroom engineering pipeline, the **Planning Canvas** (`planning/<name>.md`) bridges literate High-Level Specifications (`high/<name>.md`) and formal Low-Level Python interface stubs (`low/<name>.pyi`) before formal Groundtalk logic (`grounding/<name>.gt`), runtime library code (`lib/*.py`), or deterministic unit tests (`tests/*_test.py`) are created.

```
┌─────────────────────────────────┐
│ High-Level Spec (high/*.md)     │
└──────────────┬──────────────────┘
               │  extract, factor, weave
               ▼
┌─────────────────────────────────┐
│ Planning Canvas (planning/*)    │  <-- Intent, Typing Requirements, Contract Requirements,
└──────────────┬──────────────────┘      Woven Interactions (flat list with citations)
               │  determine types & operations; assign Invariants / Preconditions / Postconditions
               ▼
┌─────────────────────────────────┐
│ Low-Level Stubs (low/*.pyi)     │  <-- Types, Lifecycles, INVARIANTS, PRECONDITIONS, POSTCONDITIONS
└──────────────┬──────────────────┘
               │  compile into Groundtalk logic & bridge predicates
               ▼
┌─────────────────────────────────┐
│ Groundtalk Specs (grounding/*.gt)│ <-- Feasibility verification & reachability solver
└──────────────┬──────────────────┘
               │  implement & test
               ▼
┌─────────────────────────────────┐
│ Library & Tests (lib/, test/)   │
└─────────────────────────────────┘
```

The core objective of the Planning Canvas is **knowledge organization and semantic factorization**:
1. **Purging Intent from Contracts**: Removing architectural rationale, user experience motivations, and context window preservation notes from behavioral contracts into a dedicated prose section (`## Intent`), preventing "why" clauses from contaminating technical requirements.
2. **Factoring into Typing and Contract Requirements**: Decomposing high-level prose narrative into static typing requirements under `### Typing` and atomic contract requirements under `### Contracts`. Polarity (precondition, assumption, invariant, postcondition) is not assigned via manual section partitions in planning; it is inferrable from the natural language of the requirement.
3. **Eliminating Conjunctions**: Ensuring every factored contract statement is strictly atomic with zero coordinating or correlative conjunctions (`and`, `or`, `as well as`), preventing hidden multi-part obligations from obscuring verification.
4. **Weaving Cross-Cutting Interactions Without Tables**: Synthesizing interacting contracts (both within the component and from imported modules) into a flat bullet list of concrete operational outcomes with bracketed slug citations (`## Woven Contracts`), strictly avoiding markdown tables for LLM consumption.
5. **No Premature Predicates**: Relational predicate declarations, Groundtalk facts, and Datalog syntax are excluded from planning specifications, keeping planning focused on semantic domain requirements.

---

## 2. The Canonical Sections of the Planning Canvas

Every planning specification is structured into three canonical sections:

```markdown
# <name> <component_type> component

imports: <imported_modules>
implements: <implemented_interfaces>  # (implementation components only)

## Intent
[Continuous prose paragraphs]

## Factored Contracts
### Typing
[Structural typing facts expressible in AST types: - <sentence>.]
### Contracts
[Atomic contract requirements with unique semantic slugs: - <sentence>. [<slug>]]

## Woven Contracts
[Flat bullet list with bracketed slug citations: - <sentence>. [<citations>]; no ceremonies or tables]
```

### 2.1 Intent Specification (`## Intent`)

Architectural intent, conversational UX motivations, token budget economics, and multi-turn lifecycle rationale are vital for human and LLM comprehension. However, embedding intent directly into behavioral requirements (e.g., *"Executing a tool produces a suppression key to hide prior conversation turns and conserve agent context window capacity"*) creates conflated contracts where solvers and test linters cannot distinguish the binding behavioral guarantee from the architectural justification.

**Rules for Intent**:
- The `## Intent` section captures high-level design rationale, domain background, conversational turn minimization, and context management in **continuous prose paragraphs**.
- Sub-headers (`###`) are strictly prohibited under `## Intent`.
- Factored contracts and woven contracts must be completely purged of intent clauses, justification phrases ("in order to", "so that", "to indicate"), and background explanations.

### 2.2 Factored Contracts (`## Factored Contracts`)

Factored contracts take the narrative prose of `high/<name>.md` and atomize it into distinct, single-fact statements categorized across static types and the five formal Groundtalk reachability categories:

```
                           ┌────────────────────────┐
                           │   Factored Contracts   │
                           └───────────┬────────────┘
                                       │
     ┌──────────────┬──────────────┬───┴──────────┬──────────────┬──────────────┐
     ▼              ▼              ▼              ▼              ▼              ▼
   Typing      Antecedents    Assumptions    Implements     Provisions    Requirements
(Signatures)     (Caller)     (Local Env)   (Realization)   (Exported)      (Internal)
```

1. **`### Typing` (Static Type Structure & Signatures)**:
   - Structural facts expressible solely in type signatures (e.g., record fields, dataclass properties, parameter models, type parameters, and closed variant sets).
   - *Never Woven & No Slugs*: Typing facts represent static AST schema declarations, do not participate in reachability weaving, and are never cited; therefore, items under `### Typing` omit bracketed slugs.
   - *Set Conjunctions Preserved*: While conjunctions expressing distinct truths must be expanded, conjunctions expressing a closed set (such as wire type variants) express a single set definition and cannot be separated.
   - *Omitted in Implementations*: Implementation specifications (`planning/<name>_impl.md`) omit `### Typing` unless specifying private internal data structures, as public domain types are owned exclusively by interface components. Unpopulated categories under `## Factored Contracts` are omitted rather than left with empty headers.
2. **`### Antecedents` (Caller Prerequisites)**:
   - Conditions, types, parameters, or lifecycle phases that callers must satisfy before invoking an operation (e.g., the agent supplies wire parameter bindings when calling a tool).
   - Must be verified by the solver at call sites across the reachability DAG.
3. **`### Assumptions` (Scoped Environmental Invariants)**:
   - Invariants accepted within that specific construct without caller reachability proof (e.g., unique names within a registered collection, acyclic dependency graphs).
   - *Axiomatic Isolation*: Assumptions must be locally scoped to the construct that declares them, never declared as global axioms. If `unique(name)` were globally axiomatic, `one_by_name(collection, entity, name)` would be provable for any collection, even where collisions exist.
4. **`### Implements` (Intrinsic Realization)**:
   - Behavioral realization constructed directly by this component (e.g., identity parameter type converts wire values to python values without failure; tool manager installs tools).
   - Exported to callers as available capabilities; not proven locally via collaborator delegation.
5. **`### Provisions` (Exported Guarantees)**:
   - Services, guarantees, or observable state produced locally by delegating to collaborators, made available to callers (e.g., a tool manager provides installed tools; a tool call produces a tool response).
   - Must be proven locally by the solver and exported in reachability closure.
6. **`### Requirements` (Internal Obligations & Terminal Sinks)**:
   - Internal obligations, constituent constraints, and terminal outcome sinks that the component must satisfy internally (e.g., resolving symbols, converting arguments, checking requirements, or communicating diagnostic feedback on failure).
   - Must be proven locally by the solver, but are not exported as external services to callers.

### 2.3 The Zero-Conjunction Rule

In legacy specifications, requirements were frequently bundled with conjunctions:
> *Legacy Anti-Pattern*: "A dictionary parameter type converts dictionaries using key and element parameter types, providing feedback when conversion fails."

This sentence combines:
- Dictionary key conversion.
- Dictionary value conversion.
- Failure feedback generation.

When a downstream forward chainer attempts to prove reachability or diagnose a missing capability, compound sentences cause **Failure Explanation Asymmetry**: the solver cannot report whether key conversion, value conversion, or failure feedback was the unsatisfied condition.

**The Rule**:
- Every reachability factored contract item is a single bullet sentence ending with a period followed by its unique bracketed snake_case slug: `- <sentence>. [<slug>]`. Items under `### Typing` omit slugs: `- <sentence>.`. Numbered lists are prohibited; semantic slugs provide immutable identifiers immune to insertion and deletion cascades.
- Coordinating conjunctions (`and`, `or`), correlative conjunctions (`both ... and`), and compound phrases (`as well as`) are **strictly prohibited** in factored contracts when combining multiple independent truths or distinct obligations.
- Multiple actions, composite arguments, or alternative states must be split into distinct atomic bullet points:
  - *Atomic Fact 1*: `A dictionary parameter type converts dictionary keys with a key parameter type. [convert_dict_keys]`
  - *Atomic Fact 2*: `A dictionary parameter type converts dictionary values with an element parameter type. [convert_dict_vals]`
  - *Atomic Fact 3*: `A parameter type provides feedback on conversion failure. [convert_failure_feedback]`
- **The Set Definition Exception**: When a conjunction expresses a closed set, union, or variant enumeration (e.g., `Wire types are limited to wire strings, wire integers, wire booleans, wire floats, wire lists, and wire dictionaries.`), it defines a single set rather than repetition of truth. Splitting a set definition into fragmented atomic lines would falsify the statement; therefore, set-expressing conjunctions cannot and must not be separated.

### 2.4 Woven Contracts (`## Woven Contracts`)

While factored contracts isolate individual atoms of behavior, real software emerges from the **interaction** of multiple contracts. Cross-cutting rules (such as parameter validation triggering diagnostic feedback, or default value substitution occurring when an optional parameter is omitted) involve multiple factored contracts acting together.

Under `## Woven Contracts`, these interactions are explicitly synthesized into concrete operational behaviors, failure outcomes, and dispatch paths, partitioned across the five Groundtalk reachability categories (`### Assumptions`, `### Antecedents`, `### Implements`, `### Provisions`, and `### Requirements`). Categories without entries are omitted rather than left with empty headers.

#### The Category Lattice Rule for Woven Contracts

Woven contracts synthesize interacting factored contracts. The reachability category of a woven contract is determined by the **maximum (highest) category** among its constituent factored contracts according to the reachability lattice:

$$\text{Antecedents} < \text{Assumptions} < \text{Implements} < \text{Provisions} < \text{Requirements}$$

$$\text{Category}(\text{woven}) = \max_{c \in \text{constituents}} \text{Category}(c)$$

- **`Typing` contracts are never woven**: Static type declarations do not participate in interaction weaving.
- If a woven contract weaves an `Implements` with an `Assumption` (e.g., tool installation assuming unique names), $\max(\text{Assumptions}, \text{Implements}) = \text{Implements}$, placing it under `### Implements`.
- If a woven contract weaves any constituent that is a `Requirement` (such as validation checks, diagnostic failure feedback, or dispatch rules), the requirement obligation dominates ($\max = \text{Requirements}$), placing it under `### Requirements`.
- A woven contract belongs under `### Provisions` only if its highest constituent is a `Provision` (e.g., suppression key handling or follow-up tool call prediction).

#### The Reachability Categorization & Flat Bullet List Rules (No Markdown Tables)

While tabular grids (e.g. matrices with columns for Condition, Interaction, Outcome) seem visually appealing to human readers, **markdown tables are an anti-pattern for LLM-driven software engineering**:
1. **Tokenization Boundary Artifacts**: Pipe characters (`|`) break sub-word token chunks in unpredictable ways, degrading LLM attention over column contents.
2. **Column Misalignment**: In large specifications, table columns easily wrap or misalign, causing LLMs to transpose condition cells with outcome cells.
3. **Impaired Citation Verification**: LLM role agents (such as test authoring agents) struggle to cite row/column coordinates reliably compared to unambiguous bullet sentences.

**The Rules**:
- `## Woven Contracts` is partitioned into the five Groundtalk reachability categories in order: `### Antecedents`, `### Assumptions`, `### Implements`, `### Provisions`, and `### Requirements`. Unpopulated categories are omitted.
- Within each category, items are formatted strictly as a **flat bullet list** (`- `). Markdown tables (`|`) are strictly prohibited throughout the document.
- Each bullet point is a complete, self-contained English sentence ending with a period followed by its bracketed citation list without parentheses or ceremony (`(woven from ...)` is prohibited).
- Local constituent citations list bare slugs; imported citations group under their component name:
  `- When a call omits a non-required parameter specifying a default value, the default value is bound for the call. [apply_defaults, call_with_python_bindings]`
  `- When executing a tool with arguments, raw argument mappings are converted into wire parameter bindings and the tool is executed by name. [raw_args_input, convert_raw_args, delegate_raw_args, tool_provider: [wire_bindings_input, call_by_name]]`

### 2.5 Grounding Seeds (`## Grounding Seeds`)

The planning canvas does not introduce Python AST classes, methods, or type signatures—that is the exclusive role of the Grounding stub (`grounding/*.pyi`). Instead, the planning canvas extracts and stages candidate **relational vocabulary** as grounding seeds.

**First-Order Relational Model**:
- Non-type concepts and relationships are modeled as first-order relations: `relation_name(term1, term2, ...)`.
- Unary data types (`tool(t)`, `parameter(p)`) are excluded from seeds; types are handled by Python type annotations in the stub.
- Relational predicates are **element-wise**: relations relate individual entities and attributes (e.g. `parameter(tool, param)`, `name(tool, str)`), rather than treating data records as monolithic blobs.
- **Collaborator Decoupling (Collaborators as Antecedents, NEVER Arguments)**: Relational predicates decouple domain entities and capabilities from collaborator service identities. Collaborator singletons, service providers, and managers (e.g. `dag_storage`, `tool_provider`, `edit_manager`) must NEVER appear as arguments in grounding seed predicates. Collaborators appear strictly as Horn clause antecedents in reachability rules:
  $$\text{dag\_node}(n) \land \text{dag\_storage}(s) \implies \text{register\_dependents}(n)$$
  Embedding collaborator handles into predicate signatures (such as $\text{register\_dependents}(s, n)$ or $\text{install}(mgr, t)$) is prohibited; it conflates the capability with the collaborator wiring that provides it.
- **Predicates Indicate Accessibility to Knowledge or Actions (NOT Execution)**: The derivation of a ground relation in Groundtalk denotes that knowledge custody or action capability is accessible within the active scope, NOT imperative execution or runtime boolean evaluation:
  - *Knowledge Access*: $\text{node\_unit}(n, u)$ and $\text{node\_role}(n, r)$ assert accessible custody of unit and role; $\text{node\_dirty}(n, d)$ asserts accessible capability to query the dirty status $d$. Queries and observable properties include their output term: $\text{predicate}(\text{input}_1, \dots, \text{result})$.
  - *Action Access*: $\text{register\_dependents}(n)$ asserts the accessible capability to register dependents for node $n$; $\text{install}(t)$ asserts the accessible capability to register tool $t$. Deriving an action predicate does not mean the system is executing the action; it proves that the scope has verified access to perform the action.
- **Binary Accessor Predicates for Records**: For product types (dataclasses/records), Groundtalk mandates binary accessor predicates relating the instance to an individual field element-wise: $\text{entity\_property}(\text{instance}, \text{value})$.
  - Examples: $\text{node\_unit}(\text{node}, \text{unit})$, $\text{node\_role}(\text{node}, \text{role})$, $\text{file\_workspace\_path}(\text{alias}, \text{ws\_path})$, $\text{file\_owning\_node}(\text{alias}, \text{node})$, $\text{node\_dependencies}(\text{node}, \text{dep})$, $\text{dependency\_silent}(\text{dep}, \text{is\_silent})$.
  - Compound product tuples ($\text{record}(\text{inst}, f_1, f_2, \dots)$) are avoided to maintain arity stability, eliminate wildcard variables, align with the zero-conjunction rule, and map 1:1 to Python attribute accesses.
- **Entity-Prefixed Accessor Naming Rule (`<entity>_<attribute>`)**:
  - Binary accessors must explicitly scope the attribute to its enclosing entity using the `<entity>_<attribute>(inst, field)` naming pattern (e.g. `host_path_string(host_path, str)`, `node_role(node, role)`, `tool_parameter(tool, param)`, `parameter_required(param, bool)`, `response_output(response, val)`).
  - Bare, un-prefixed nouns (`name`, `text`, `output`, `required`, `description`) and primitive type/argument names are **strictly prohibited** as predicate names. Bare names cause severe ambiguity, vocabulary collisions across components, and mislead reasoners into hallucinating incorrect relationships.
- **Method Inputs Bound by Operation Signatures (Prohibition of Input-as-Antecedent Anti-Pattern)**:
  - Input parameters provided to an operation (e.g. a string path passed to `create_workspace_path`, a tool passed to `install_tool`, or wire bindings passed to `execute_tool`) are bound directly by the method parameter signature (`param(name)`).
  - Specification authors and reasoners must **never assert bogus antecedent predicates** claiming that a managing singleton "owns" an incoming argument (e.g., prohibiting `path_string(self, path)` or `tool_parameter(self, tool)`). Managing singletons provide operational capabilities; input parameters arrive directly from callers.
- **Directional Binding Modes and Well-Moded Predicates (No Reverse Projections)**: Relational predicates model forward knowledge and action accessibility flowing from bound inputs to outputs (mode $+ \to -$). Predicates must not invent synthetic reverse projections (e.g. attempting to extract owning nodes from dependencies) or simulate fields of hypothetical downstream Python wrapper classes. Domain relationships must strictly reflect high-level specification requirements.
- **Prohibition of `is_xxx` Dynamic Type Testing**: Types and sealed variants are static AST constructs, not runtime boolean flags. Predicates like $\text{is\_change\_message}(\text{msg}, \text{is\_change})$ or $\text{is\_read\_only}(\text{file}, \text{is\_ro})$ are strictly prohibited.
- **Prohibition of Variant Dissection (Directed Horn Subtyping)**: Supertype decomposition via disjunction ($\text{dag\_message}(m) \implies \text{change\_message}(m) \lor \text{feedback\_message}(m)$) is strictly prohibited. Generic operations target the supertype relation ($\text{dag\_message}(m, \text{text})$). Subtypes satisfy supertypes via directed Horn rules ($\text{Subtype} \implies \text{Supertype}$) without case splitting.
- **Neutral Staging**: Candidate non-type predicates are listed regardless of whether they will become antecedents, assumptions, implements, provisions, or requirements in the grounding stub. The grounding stage maps them into their appropriate reachability roles.

---

## 3. Groundtalk Reachability Mapping

The five contract categories of the Planning Canvas map 1:1 into the formal Groundtalk specification clauses embedded in Python interface stubs (`grounding/*.pyi`):

| Planning Canvas Section | Groundtalk Docstring Header | Solver Proof Obligation | Scope Export |
| :--- | :--- | :--- | :--- |
| `### Assumptions` | `GROUNDING_ASSUMPTIONS:` | Unproven (Accepted as scoped invariants within construct) | Local to construct |
| `### Antecedents` | `GROUNDING_ANTECEDENTS:` | Must be verified at call sites across reachability DAG | Caller obligation |
| `### Implements` | `GROUNDING_IMPLEMENTS:` | Unproven locally (Intrinsic realization) | Exported to callers |
| `### Provisions` | `GROUNDING_PROVISIONS:` | Must be proven locally via collaborator reachability | Exported to callers |
| `### Requirements` | `GROUNDING_REQUIREMENTS:` | Must be proven locally via collaborator reachability | Local terminal sink (Not exported) |

### 3.1 Axiomatic Isolation vs. Global Assumptions

In formal logic, an assumption treated as a global axiom is universally true across the entire universe of discourse:
$$\forall x. \text{unique}(x)$$

If uniqueness were globally axiomatic, a lookup predicate such as:
$$\text{one\_by\_name}(c, e, n) \leftarrow \text{collection}(c) \land \text{member}(c, e) \land \text{name}(e, n) \land \text{unique}(n)$$
would succeed for *every* collection in the system, even collections where duplicate names exist!

By isolating `GROUNDING_ASSUMPTIONS:` locally to the construct (class or operation) that assumes it, Groundtalk ensures that the invariant holds strictly within the evaluated scope of that construct, preventing assumption leakage across unrelated components.

---

## 4. Canonical Reference Prototype: `tool_provider.md`

Below is the complete reference implementation of the Planning Canvas format, authored for the `tool_provider` interface component in `update_with_ai/parts/sandbox/planning/tool_provider.md`:

```markdown
# tool_provider interface component

imports: agent_session

## Intent

Autonomous agent loops require structured boundaries to interact safely with environment capabilities. Free-form text interfaces force fragile parsing and invite unpredictable agent deviations, while rigid crash behaviors prevent autonomous error recovery. The tool_provider interface component establishes an extensible contract between the agent orchestration layer and concrete domain tooling.

By formalizing tool schemas with explicit parameter descriptions, agents can discover and satisfy invocation requirements without guessing. Wire types decouple external serialized payloads from internal Python domain types, intercepting malformed inputs before tool execution begins. When invocations are malformed, structured diagnostic feedback provides the necessary context for the agent to self-correct in subsequent turns.

To preserve agent context window capacity across multi-turn interactions, responses can designate suppression keys to prune repetitive or superseded outputs from conversation history. For predictable multi-step workflows, responses can designate follow-up tool calls with first-person reasoning to drive immediate sequential execution without turn latency.

## Factored Contracts

### Typing

- A tool has a name.
- A tool has a description.
- A tool has a set of tool parameters.
- A tool parameter has a name.
- A tool parameter has a description.
- A tool parameter specifies a parameter type.
- A tool parameter can be designated as required.
- A non-required parameter can specify a default value.
- A required parameter can specify a missing note based on present parameters.
- Wire types are limited to wire strings, wire integers, wire booleans, wire floats, wire lists, and wire dictionaries.
- An identity parameter type specifies that the wire type matches the python type.
- A tool response provides tool output.
- A tool response communicates whether the conversation terminates.
- A tool response can provide a suppression key.
- A tool response can designate a follow-up tool call.
- A follow-up tool call specifies the next tool to call.
- A follow-up tool call specifies parameter values for the next tool.
- A follow-up tool call specifies reasoning text articulating from the agent's perspective why the next tool is called.

### Antecedents

- An agent session specifies tools to install based on the nature of the session. [session_tools_spec]
- An agent supplies wire type parameter bindings when calling a tool. [call_wire_bindings]

### Assumptions

- Installed tools in a tool manager have unique names. [unique_tool_names]
- Parameters of a tool have unique names. [unique_param_names]

### Implements

- An agent session's tool manager installs tools for the agent session. [install_tools]
- A parameter type converts wire type values to python type values. [convert_wire_val]
- An identity parameter type converts wire values to python values without failure. [convert_identity]
- A list parameter type converts lists using an element parameter type. [convert_list]
- A dictionary parameter type converts dictionary keys with a key parameter type. [convert_dict_keys]
- A dictionary parameter type converts dictionary values with an element parameter type. [convert_dict_vals]

### Provisions

- A tool manager provides installed tools. [provide_installed_tools]
- A tool call produces a tool response. [call_produces_response]
- A tool response can provide a suppression key to supersede prior conversation responses with the same key. [supersede_by_key]
- A tool response can designate a follow-up tool call predicting the agent's next action. [predict_follow_up]

### Requirements

- A parameter type provides feedback on conversion failure. [convert_failure_feedback]
- A composite parameter type formed from constituent parameter types propagates all constituent conversion failures. [composite_failure_propagate]
- A tool manager calls tools by name. [call_by_name]
- For each call, the tool manager resolves symbols. [resolve_symbols]
- For each call, the tool manager converts arguments. [convert_arguments]
- For each call, the tool manager applies default values for omitted non-required parameters. [apply_defaults]
- For each call, the tool manager checks parameter requirements. [check_requirements]
- For each call, the tool manager calls the tool with python type bindings. [call_with_python_bindings]
- A tool call fails when a tool is not called properly. [call_improper_fails]
- A tool call fails when tool-specific execution conditions fail. [exec_condition_fails]
- A failed tool call communicates diagnostic feedback in the tool response. [failed_call_feedback]

## Woven Contracts

### Implements

- When installing a tool, name collision handling is out of scope. [unique_tool_names, install_tools]

### Provisions

- When a response specifies a suppression key, prior conversation turns with the same key are hidden. [call_produces_response, supersede_by_key]
- When a subsequent call can be reliably predicted, the response designates the next tool call with parameter values and agent reasoning. [call_produces_response, predict_follow_up]

### Requirements

- Identity parameter conversion never produces conversion failure feedback. [convert_identity, convert_failure_feedback]
- When calling a tool whose name does not match any installed tool, the call fails with feedback citing the unknown tool and listing installed tools. [unique_tool_names, provide_installed_tools, call_by_name, call_improper_fails, failed_call_feedback]
- When a call omits a required parameter specifying a missing note evaluated against present parameters, the call fails with feedback citing the missing parameter and missing note. [check_requirements, call_improper_fails, failed_call_feedback]
- When a call omits a required parameter lacking a missing note, the call fails with feedback citing the missing parameter. [check_requirements, call_improper_fails, failed_call_feedback]
- When a call omits a non-required parameter specifying a default value, the default value is bound for the call. [apply_defaults, call_with_python_bindings]
- When wire conversion fails for a parameter, the call fails with feedback citing the parameter name and the conversion failure feedback. [convert_wire_val, convert_failure_feedback, convert_arguments, call_improper_fails, failed_call_feedback]
- Failure of any constituent conversion in a composite type propagates that constituent's failure feedback. [convert_list, convert_dict_keys, convert_dict_vals, convert_failure_feedback, composite_failure_propagate, convert_arguments, call_improper_fails]
- When all parameter symbols resolve, required parameters are present, defaults are applied, and wire conversions succeed, the tool is called with python type bindings and returns its tool response. [call_wire_bindings, convert_wire_val, call_produces_response, resolve_symbols, convert_arguments, apply_defaults, check_requirements, call_with_python_bindings]
- When tool-specific execution conditions fail, failure status is indicated in the tool response with diagnostic feedback. [call_produces_response, exec_condition_fails, failed_call_feedback]

## Grounding Seeds

These candidate non-type predicates represent the relational vocabulary to be formalized during grounding:

- `entity_name(entity, str)`: Relates a tool or parameter to its identifier string.
- `entity_description(entity, str)`: Relates a tool or parameter to its explanatory description string.
- `tool_parameter(tool, param)`: Relates a tool to an accepted parameter specification.
- `parameter_required(param, is_required)`: Relates a parameter to whether it must be bound in any valid tool call.
- `default_value(param, val)`: Relates an unrequired parameter to its default value applied upon omission.
- `missing_note(param, note)`: Relates a required parameter to diagnostic recovery guidance evaluated from present arguments.
- `parameter_type(param, type)`: Relates a parameter to the converter governing its wire and python representations.
- `python_type(type, py_type)`: Relates a parameter type to the concrete Python data type it produces.
- `wire_type(type, w_type)`: Relates a parameter type to the primitive wire type it accepts.
- `convert(type, actual, wire)`: Expresses successful conversion of an input wire value to an actual Python value.
- `conversion_feedback(type, feedback)`: Relates an unsuccessful conversion to its diagnostic error feedback.
- `install_tool(tool)`: Expresses the capability to register a tool into the session environment.
- `installed_tools(tools)`: Exposes the collection of currently registered tools.
- `execute_tool(tool, bindings)`: Expresses the capability to invoke a tool with resolved parameter bindings.
- `response_output(response, val)`: Relates an execution response to its primary output payload.
- `response_terminates(response, terminates)`: Relates an execution response to whether it instructs the agent conversation to end.
- `diagnostic_feedback(response, feedback)`: Relates an execution failure to its diagnostic recovery feedback.
- `suppression_key(response, key)`: Relates an execution response to a deduplication key used to hide prior conversation turns.
- `response_follow_up(response, call)`: Relates an execution response to its predicted follow-up tool call.
- `follow_up_tool(call, tool)`: Relates a follow-up tool call to its predicted next tool.
- `follow_up_params(call, params)`: Relates a follow-up tool call to its wire parameter values.
- `follow_up_reasoning(call, reasoning)`: Relates a follow-up tool call to its first-person agent reasoning text.
- `unique_names(collection, is_unique)`: Relates a collection of tools or parameters to its name uniqueness boolean.
- `one_by_name(collection, entity, name)`: Relates a named collection and name string to its uniquely resolved member entity.
```

---

## 5. Scope Attribution & Boundary Filtering

When extracting factored contracts from high-level specifications and formalizing planning canvases, clear boundary filtering and scope attribution rules must be applied:

1. **Constituent Property Enumeration vs. Requirements**:
   - Statements in prose that introduce or enumerate the fields of a data record (e.g. *"A model configuration defines model identifiers, timeouts, and iteration limits"*) define static structure.
   - These belong in Python `@dataclass(frozen=True)` type annotations during grounding, not as behavioral requirements.
2. **Static Knowledge vs. Requirements**:
   - Statements describing static type algebra or mathematical definitions (e.g. *"Concatenating a workspace root and a workspace path produces an absolute path"*) describe semantic definitions rather than observable contracts on an active component.
3. **Domain Purpose vs. Requirements**:
   - Clauses explaining the rationale of a flag or data state (e.g. *"A dependency can be silent to indicate that the dependent node does not depend on the dependency's content"*) belong exclusively under `## Intent`.
4. **Non-Vacuous Operation & Property Requirements (Inferred Implementation)**:
   - When defining or overriding an operation or property, specifications must imagine how it would be implemented; this implementation model defines the non-vacuous requirements for that operation:
     - *Root Polymorphic Interfaces*: Abstract interface methods (such as `Tool.execute_tool`) can execute arbitrary domain logic; they define polymorphic signatures without imposing narrow collaborator requirements.
     - *State-Holding Services & Internal State*: When a service defines mutators/installers (such as `ToolManager.install_tool`), it must specify a requirement that the operation updates internal manager state. Symmetrically, exposed collections (such as `ToolManager.installed_tools`) must specify a requirement that exposed items originate from internal manager state.
     - *Early Delegating Operations*: Operations whose coordination logic is fully specified and provable at the interface level (such as `ToolManager.execute_tool_by_wire` invoking `Tool.execute_tool` after converting wire arguments) capture this delegation requirement as early as the interface component.
     - *External System & Host Capabilities*: Operations that interact with the host environment (such as `ReadManager.can_read` or `ViewFileTool.execute_tool` validating and reading files) must explicitly require the requisite external capability (e.g. `read_host_file`).
5. **Collaborator Decoupling in High/Planning Contracts (No Premature Collaborator Mentioning)**:
   - High-Level and Planning specifications must **NEVER** mention collaborator singletons, managers, or peer service names (e.g., stating *"obtained from the session node config"* in `sandbox_file_reader` is strictly prohibited when `node_config` is not even part of that component's scope).
   - High and Planning requirements must express requirements in terms of abstract, decoupled capabilities: e.g., *"MUST expose declared read-only files from other objects"*.
   - Even in implementation planning specifications (`planning/<name>_impl.md`), collaborators must not be mentioned by name. Concrete collaborator resolution occurs **exclusively during grounding** (`grounding/*.gt` and `grounding/*.pyi`), where external capability origins are mapped to imported singletons within the active lifecycle tier.
6. **No Verbatim Copy-Down of Postconditions to Refinements/Subtypes**:
   - Postconditions and requirements do not need to be duplicated down to refinements, implementations, or subtypes verbatim if there are no new conditions or specialized constraints to add.
   - The grounding process and Groundtalk solver consider requirements defined on the target type and all of its ancestor supertypes transitively.
7. **Active Singletons vs. Passive Records**:
   - Operational requirements must be attributed to active singletons and polymorphic services. Passive data types define only operator-like behaviors intrinsic to values themselves (e.g. string formatting, structural equality, or pure projection).

