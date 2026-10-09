# <name> <component_type> component

<!-- if: has_imports -->
imports: <imported_modules>
<!-- endif -->
<!-- if: needs_implements -->
implements: <implemented_interfaces>
<!-- endif -->

## Intent

<TODO: continuous prose paragraphs explaining architectural rationale, UX motivations, and trade-offs.>

## Factored Contracts

### Typing

- <TODO: static structural types, record fields, variants: - <sentence>.>.

### Contracts

- <TODO: atomic behavioral contracts with unique semantic slugs: - <sentence>. [<slug>]>.

### Woven Contracts

- <TODO: synthesized cross-cutting interactions with bracketed slug citations: - <sentence>. [<citations>]>.

## Grounding

### Knowledge Provisions

- <TODO: exported capabilities with unique slugs: - <sentence>. [<slug>]>.

<!-- if: needs_implements -->
### Inherited Deferred Requirements

- <TODO: for _impl: verbatim repetition of interface deferrals: - <sentence>.
  - Grounded: [<slugs>]>
<!-- endif -->

### Knowledge Requirements

- <TODO: consumer obligations without slugs: - <sentence>.
  - Grounded: [<slugs>] or - Deferred: <rationale>>
