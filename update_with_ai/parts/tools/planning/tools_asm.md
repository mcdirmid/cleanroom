<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 7ca5af56ab58
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# tools_asm assembly component

imports: tool_coverage_impl

## Intent

Assembles tool and inspection services, including module statement test coverage evaluation, into the tools package.

## Factored Contracts

### Contracts

- Assembles tools service implementations into the agent session lifecycle tier. [assemble_tools_services]

## Grounding

### Knowledge Provisions

- Aggregated tools session assembly ready for orchestration. [tools_assembly_provision]

### Knowledge Requirements

- Integration of constituent tools services into lifecycle tier.
  - Grounded: [tools_assembly_provision]
