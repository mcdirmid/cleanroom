# Architecture & Design: Failure Analysis, Pure Datalog Proofs, and Symbols

## Executive Summary
This design document records the failure analysis of past approaches (blind Datalog forward-chaining, SSA imperative dataflow simulation, and hallucinated proof givens), and presents the unified architectural design for Groundtalk: **Pure Relational Datalog with Explicit Output Modes (`out`), Reified Symbols (`symbol Name`), and Generic Type Judgments (`has_type(val, TypeSymbol)`)**.

---

## 1. Things Tried That Failed

### 1.1 Failure 1: The SSA "Typed Dataflow" Evaluator
- **What was attempted**: To make `execute_tool_req` readable, we wrote proofs using imperative SSA syntax:
  ```groundtalk
  proof [execute_tool_req] response: ToolResponse = ToolManager.execute_tool(name, {param_name: param_value}):
    1. tool = ToolManager.installed_tools.get(name)
    1. param = tool.parameters.get(param_name)
    1. actual_value = param.parameter_type.convert(param_value)
    1. response = tool.execute_tool({param: actual_value})
    qed
  ```
  We then tried to treat this as an expression language, building a typed dataflow evaluator and expression compiler into Groundtalk.
- **Why it failed**:
  - **Category Mistake**: Groundtalk is a relational Datalog engine, not an imperative compiler or typed expression evaluator. Trying to evaluate nested expressions, dictionaries, and dot-accesses turned the verifier into an ad-hoc Python interpreter.
  - **Lost Relational Foundation**: It obscured the fact that `x = f(y)` is simply the functional notation for the 2-place relation `f(y, x)`.
  - **Solver Incompatibility**: Datalog solvers could not reason about, unify, or backward-chain through expression ASTs without complex re-encoding.

### 1.2 Failure 2: Blind Forward-Chaining Reachability
- **What was attempted**: Saturating facts forward from the caller's inputs (`ToolManager.execute_tool(name, wire_args)`) using standard semi-naive Datalog forward reachability.
- **Why it failed**:
  - In a method execution, intermediate objects (like `tool = tools.get(name)` or `pt = param.parameter_type`) are **existential terms** created during execution, not static database facts.
  - Forward chaining from `(name, wire_args)` stops immediately because without knowing the goal (`ToolResponse`), the engine has no reason to fire dictionary lookups or parameter conversions. The reachable horizon stalled at step 0.

### 1.3 Failure 3: Mechanistic Fraud via Hallucinated Givens
- **What was attempted**: To get `execute_tool_req` past the linter, the proof was written with ungrounded `given` assertions:
  ```groundtalk
  proof [execute_tool_req]:
    1. ToolManager.execute_tool(name, wire_parameter_bindings, response) given
    2. installed_tools(tools)                                            given
    3. Tool(tool)                                                        given  <-- UNGROUNDED!
    4. ParameterType(param_type)                                         given  <-- COMPLETELY FABRICATED!
    5. ParameterType.convert(wire_value, actual_value)                   by param_type_convert_cap(4)
    6. Tool.execute_tool(actual_parameter_bindings, response)            by tool_exec_cap(3)
    7. ToolResponse(response)                                            by tool_exec_req(6)
    qed
  ```
- **Why it failed**:
  - `Tool(tool)` and `ParameterType(param_type)` were asserted out of nowhere. Neither was passed by the caller or provided as an entry given.
  - This was a purely syntactic constraint-satisfaction game that violated semantic soundness.

### 1.4 Failure 4: Premature Variable Binding in Requirement Heads
- **What was attempted**:
  ```groundtalk
  [execute_tool_req] ToolResponse(response), Tool.execute_tool(actual_parameter_bindings, response), ParameterType.convert(wire_value, actual_value) <-?
      ToolManager.execute_tool(name, wire_parameter_bindings, response),
      installed_tools(tools) .
  ```
- **Why it failed**:
  - The requirement forced specific variable names (`actual_parameter_bindings`, `wire_value`, `actual_value`) onto the LHS without stating how they connect to the RHS.
  - Also, `installed_tools(tools)` was placed in the requirement antecedent `<-?` as if the *caller* provided the tool manager's private state! The caller only calls `ToolManager.execute_tool(name, wire_bindings, out response)`; access to `installed_tools` is an internal instance capability.

---

## 2. The Sound Foundation: Pure Relational Datalog

The insight is that **SSA is purely syntactic sugar for functional relational predicates**:
$$y = f(x) \iff f(x, \text{out } y)$$

We do not need a foreign expression language or typed dataflow engine. We can express the entire execution, verification, and goal search directly in pure Datalog.

### 2.1 Explicit Output Modes (`out`)
In logic programming, predicates relate inputs to outputs. We explicitly mark output positions with the keyword `out`:
- In declarations:
  ```groundtalk
  decl Mapping.get(map, key, out value)
  decl Tool.parameters(tool, out parameters)
  decl ParameterType.convert(pt, wire_value, out actual_value)
  decl Tool.execute_tool(tool, actual_bindings, out response)
  ```
- In proofs:
  ```groundtalk
  8. Mapping.get(tools, name, out tool)                      by map_get(7, 3)
  ```
- **Well-Groundedness Enforcement**:
  Every non-`out` argument must be already ground in the known environment at step $k$. An argument marked `out` is fresh and becomes ground at step $k$. This prevents hallucinating terms.

### 2.2 Reified Type Symbols (`symbol Name`) and `has_type`
Instead of rigid unary sort predicates (`Tool(x)`, `ToolParameter(p)`), types are reified as **symbols**:
```groundtalk
PREDICATES:
- symbol ToolName
- symbol ParameterName
- symbol WireType
- symbol Tool
- symbol ToolParameter
- symbol ToolResponse
- symbol ToolManager
```
Typing is expressed via the binary relation:
$$\text{has\_type}(term, \text{TypeSymbol})$$

#### Why This Works: Generic Collections in First-Order Datalog
Because types are values/symbols, we can write universal axioms for generics in `core.gt` without duplicating predicates:
```groundtalk
Mapping.key(map, out key)       <- has_type(map, Mapping) .
has_type(key, T)                <- Mapping.KT_co(map, T), Mapping.key(map, key) .
Mapping.get(map, key, out value)<- has_type(map, Mapping), Mapping.KT_co(map, T), has_type(key, T) .
has_type(value, T)              <- Mapping.get(map, _, value), Mapping.VT_co(map, T) .
```

### 2.3 Generalized State Invariants (`state field(var) <- scope where invariants`)
Instead of ad-hoc colon syntax (`installed_tools : Tool in ToolManager .`), state fields are declared as scoped resource invariants in a `STATE:` section placed below `PREDICATES:`:
```groundtalk
STATE:
state installed_tools(tools) <- singleton(ToolManager) where has_type(tools, Mapping), Mapping.KT_co(tools, ToolName), Mapping.VT_co(tools, Tool)
```
- **State Predicate**: `installed_tools(tools)` defines the state predicate over its parameter term(s).
- **Access Scope**: The antecedent `<- singleton(ToolManager)` defines the capability/custody context required to access or mutate this state.
- **Invariant (`where`)**: The clause following `where` specifies the arbitrary relational invariants that govern the state variables:
  - **On Write (Contravariant Precondition)**: To assert a state write `+installed_tools(tools)`, callers must provide evidence for all facts in the `where` clause (`has_type(tools, Mapping), Mapping.KT_co(tools, ToolName), Mapping.VT_co(tools, Tool)`) alongside holding the access scope (`singleton(ToolManager)`).
  - **On Read (Covariant Postcondition)**: When querying or reading `installed_tools(tools)`, callers obtain all facts in the `where` clause for free.
- **Generalization**: Multiple parameters and multi-fact relational constraints are supported naturally:
  ```groundtalk
  state node_parents(node, parent) <- singleton(DagStorage) 
      where has_type(node, Node), has_type(parent, Node), acyclic_edge(node, parent)
  ```

### 2.4 Wildcards (`_`) for Unbound Consequent Terms
In requirement consequents (`Consequents <-? Antecedents`), terms that are not bound by any antecedent premise are existential. Naming them with an arbitrary identifier like `tools` falsely suggests a specific binding:
```groundtalk
% Bad: 'tools' is unbound in antecedents:
- [install_tool_req] +installed_tools(tools) <-? ToolManager.install_tool(tool) .

% Correct: Unbound consequent terms must use '_':
- [install_tool_req] +installed_tools(_) <-? ToolManager.install_tool(tool) .
```
The verifier enforces that any variable in a requirement consequent not bound by antecedent premises must be written as `_`.

### 2.5 Bi-Conditional Access Rules (`<->`) and Single-Given Proofs
Interface member access rules are derived as bi-conditionals (`<->`), encoding invocation validity in both directions:
1. **Forward ($\leftarrow$)**: Calling an operation requires holding its receiver sort/capability and having properly-typed arguments.
2. **Reverse ($\rightarrow$)**: Being inside the execution of an operation mathematically guarantees that the caller possessed the receiver sort and all input argument types.

```groundtalk
- [tool_manager_installed_tools_access] ToolManager.installed_tools(_) <-> singleton(ToolManager) .
- [tool_manager_install_tool_access] ToolManager.install_tool(tool) <-> singleton(ToolManager), has_type(tool, Tool) .
- [tool_manager_execute_tool_access] ToolManager.execute_tool(name, wire_parameter_bindings, _) <->
    singleton(ToolManager),
    has_type(name, ToolName),
    has_type(wire_parameter_bindings, Mapping),
    Mapping.KT_co(wire_parameter_bindings, str),
    Mapping.VT_co(wire_parameter_bindings, WireType) .
```

Because of the reverse rules, **the operation invocation itself is the ONLY given in the proof**. All entry preconditions (receiver custody, argument types, collection type parameters) are derived directly from the invocation using the bi-conditional access rule.

### 2.6 State Reading, Writing, and Property Getters
State declared under `STATE:` represents internal managed resources:
```groundtalk
STATE:
state installed_tools(tools) <- singleton(ToolManager) where has_type(tools, Mapping), Mapping.KT_co(tools, ToolName), Mapping.VT_co(tools, Tool)
```
- **Writing State (`+installed_tools`)**: Mutators like `install_tool` write state. In the requirement, `+installed_tools(_)` expresses the write effect. In the proof, the author proves the scope and all `where` invariants, then establishes `+installed_tools(tools)` via `state_write:installed_tools`.
- **Reading State**: The state fact `installed_tools(tools)` is accessed via `state_access:installed_tools`, which requires custody of `singleton(ToolManager)`. Once accessed, `state_read:installed_tools` yields all `where` invariants for free.
- **Property Getters**: A property getter like `ToolManager.installed_tools(out tools)` exposes the internal state to callers:
  ```groundtalk
  - [tool_manager_installed_tools_req] installed_tools(tools) <-? ToolManager.installed_tools(out tools) .
  ```
  The return type requirement `tool_manager_installed_tools_type` is proven directly from the state invariant via `state_read:installed_tools`.

### 2.7 Verified Pure Datalog Proofs
```groundtalk
proof [install_tool_req]:
  1. ToolManager.install_tool(tool)                                        given
  2. singleton(ToolManager)                                                by tool_manager_install_tool_access(1)
  3. has_type(tool, Tool)                                                  by tool_manager_install_tool_access(1)
  4. Tool.name(tool, out name)                                             by tool_name_access(3)
  5. has_type(name, ToolName)                                              by tool_name_type(4)
  6. Mapping.make(name, tool, out tools)                                    by mapping_make_cap()
  7. has_type(tools, Mapping)                                              by mapping_make_axiom(6, 5, 3)
  8. Mapping.KT_co(tools, ToolName)                                        by mapping_make_axiom(6, 5, 3)
  9. Mapping.VT_co(tools, Tool)                                            by mapping_make_axiom(6, 5, 3)
  10. +installed_tools(tools)                                              by state_write:installed_tools(2, 7, 8, 9)
  qed

proof [tool_manager_installed_tools_req]:
  1. ToolManager.installed_tools(out tools)                                given
  2. singleton(ToolManager)                                                by tool_manager_installed_tools_access(1)
  3. installed_tools(tools)                                                by state_access:installed_tools(2)
  qed

proof [execute_tool_req]:
  1. ToolManager.execute_tool(name, wire_parameter_bindings, out response)  given
  2. singleton(ToolManager)                                                by tool_manager_execute_tool_access(1)
  3. has_type(name, ToolName)                                               by tool_manager_execute_tool_access(1)
  4. has_type(wire_parameter_bindings, Mapping)                             by tool_manager_execute_tool_access(1)
  5. Mapping.KT_co(wire_parameter_bindings, str)                           by tool_manager_execute_tool_access(1)
  6. Mapping.VT_co(wire_parameter_bindings, WireType)                       by tool_manager_execute_tool_access(1)
  7. installed_tools(tools)                                                by state_access:installed_tools(2)
  8. has_type(tools, Mapping)                                              by state_read:installed_tools(2, 7)
  9. Mapping.KT_co(tools, ToolName)                                        by state_read:installed_tools(2, 7)
  10. Mapping.VT_co(tools, Tool)                                            by state_read:installed_tools(2, 7)
  11. Mapping.get(tools, name, out tool)                                   by mapping_get_axiom(8, 9, 3)
  12. has_type(tool, Tool)                                                 by mapping_get_type(11, 10)
  13. Tool.parameters(tool, out parameters)                                by tool_parameters_access(12)
  14. has_type(parameters, Mapping)                                        by tool_parameters_type(13)
  15. Mapping.KT_co(parameters, str)                                        by tool_parameters_type(13)
  16. Mapping.VT_co(parameters, ToolParameter)                             by tool_parameters_type(13)
  17. Mapping.key(wire_parameter_bindings, out param_name)                  by mapping_key_axiom(4)
  18. has_type(param_name, str)                                            by mapping_key_type(5, 17)
  19. Mapping.get(wire_parameter_bindings, param_name, out wire_value)      by mapping_get_axiom(4, 5, 18)
  20. Mapping.get(parameters, param_name, out param)                       by mapping_get_axiom(14, 15, 18)
  21. has_type(param, ToolParameter)                                       by mapping_get_type(20, 16)
  22. ToolParameter.parameter_type(param, out pt)                          by tool_parameter_parameter_type_access(21)
  23. has_type(pt, ParameterType)                                          by tool_parameter_parameter_type_type(22)
  24. ParameterType.convert(pt, wire_value, out actual_value)              by parameter_type_convert_access(23)
  25. Mapping.make(param, actual_value, out actual_bindings)               by mapping_make_cap()
  26. Tool.execute_tool(tool, actual_bindings, out response)               by tool_execute_tool_access(12)
  27. has_type(response, ToolResponse)                                     by tool_execute_tool_type(26)
  qed
```
- **100% Pure Datalog**: Every step is a relational atom.
- **Mechanically Derived Rules**: Member accessibility (`[..._access]`) and type requirements (`[..._type]`) are mechanically generated directly from interface `.pyi` definitions.
- **Deterministic**: Backward resolution from `response: ToolResponse` forces `Tool.execute_tool`, which forces `Tool`, which forces lookup in `installed_tools`.

---

## 3. Standard Library: `core.gt`

A dedicated canonical specification `core.gt` is automatically included in every Groundtalk evaluation:
- **Location**: `update_python_with_ai/support/lib/core.gt` (and mirrored in `update_with_ai/support/lib/core.gt`).
- **Contents**:
  - Declarations for built-in symbols: `SystemTier`, `Mapping`, `Sequence`, `Set`, `Optional`, `Any`, `str`, `int`, `bool`.
  - Built-in predicates: `Mapping.get`, `Mapping.key`, `Mapping.make`, `Mapping.KT_co`, `Mapping.VT_co`, `has_type`, `singleton`, `lifecycle_tier`.
  - Axioms for generic map access, key projection, and type propagation.
