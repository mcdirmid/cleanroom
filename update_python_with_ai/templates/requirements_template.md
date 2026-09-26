# <name> <component_type> component

imports: <imported_modules>
<!-- if: needs_implements -->
implements: <implemented_interfaces>
<!-- endif -->

## Assumptions and Requirements

<!-- if: has_assumptions -->
### Assumptions

1. <TODO: caller preconditions or environmental invariants; failure results in undefined behavior.>
<!-- endif -->

### Requirements

1. <TODO: guaranteed behavioral contracts, observable outcomes, state transitions, or explicit failure handling.>

## Grounding Facts

### Knowledge Needed

- <TODO: in prose, describe inputs, environment variables, default constants, or state required to achieve the requirements.>

### Actions Needed

- <TODO: in prose, describe external collaborator operations, boundary calls, or transformations needed to achieve the requirements.>

<!--
TODO: work through this template section by section:
  - extract atomic, single-sentence requirements from the High-Level Specification (high/<name>.md)
  - separate caller preconditions (Assumptions) from binding guarantees (Requirements)
  - plan grounding facts in plain prose under Knowledge Needed and Actions Needed to prevent premature AST pattern matching
  - every requirement sentence must end with a period
  - avoid formula language, AST variables (v_call, v_param), and quantifiers (for any, there exists)
  - delete this comment block when the document is complete
-->

