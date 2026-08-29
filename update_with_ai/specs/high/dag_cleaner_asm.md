# dag_cleaner_asm

fulfills: dag_cleaner
imports: dag_cleaner_impl (topological cleaning)

## Deltas

- Assembles the concrete DAG cleaner implementation over a supplied graph storage and clean logic.
- [boundary] The concrete DAG cleaner implementation is selected here.
- [external] The concrete component implementation.

## Non-concerns

- Consumption: how the assembled DAG cleaner is used is unspecified here.
- Selection policy: the concrete implementations wired here are a default assembly; other selections may differ.
- Testability: this assembly is never tested; it performs no functionality beyond configuration and assembly of other modules.
