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
