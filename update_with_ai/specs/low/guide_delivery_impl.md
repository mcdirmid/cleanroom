<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - guide_delivery.md
-->

# Implementation LLS: guide_delivery_impl

## Data Types
```python
from guide_delivery import GuideDelivery, GuideDeliveryFactory, TaskGuide

class _GuideDeliveryImpl(GuideDelivery):
    def __init__(self, guide: TaskGuide) -> None: ...

class GuideDeliveryFactoryImpl(GuideDeliveryFactory):
    def __init__(self) -> None: ...
```

## Behavioral Description

- `GuideDeliveryFactoryImpl.create_guide_delivery` constructs a `GuideDelivery` initialized with `guide`.
- The internal `GuideDelivery` implementation parses guide Markdown headings into step sections, skipping sections headed by `## Lint checks`.
- Pre-injects the guide summary as a startup `StepDelivery`.
- Advances to subsequent step sections only upon receiving `verification_passed=True`.
- Retains the active step section without advancement when verification fails.

## Invariants

- Step sections advance strictly sequentially.
- Sections headed by `## Lint checks` are excluded from step delivery.
- Failing verification retains the current step section without advancement.
