<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 69199601d4ed
SPEC_QA_AUDIT: 2026-10-07T23:58:18Z
-->

# loop_asm assembly component

imports: loop_cleaner_impl, loop_guard_impl, loop_node_cleaner_impl, openai_conversation_impl, openai_driver_impl

## Intent

Assembles turn loop execution, prompt conversation history formatting, loop guard repetition tracking, subgraph iteration, and node cleaning orchestration into the loop subsystem assembly.

## Factored Contracts

### Contracts

- Assembles loop service implementations into the system lifecycle tier. [assemble_loop_services]

## Grounding

### Knowledge Provisions

- Aggregated loop subsystem assembly ready for orchestration. [loop_assembly_provision]

### Knowledge Requirements

- Integration of constituent loop services into lifecycle tier.
  - Grounded: [loop_assembly_provision]
