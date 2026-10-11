<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:03Z
LAST_CHANGED: 2026-10-11T04:12:06Z
CHANGE: Move the tools assembly to the system lifecycle tier
CODE_HASH: c9e640f8b270
SPEC_QA_AUDIT: 2026-10-11T22:09:03Z
-->

# tools_asm assembly component

## Intent

Assembles tool and inspection services, including module statement test coverage evaluation, into the tools package.

## Factored Contracts

### Contracts

- Assembles tools service implementations into the system lifecycle tier. [assemble_tools_services]

## Grounding

### Knowledge Provisions

- Aggregated tools session assembly ready for orchestration. [tools_assembly_provision]

### Knowledge Requirements

- Integration of constituent tools services into lifecycle tier.
  - Grounded: [tools_assembly_provision]
