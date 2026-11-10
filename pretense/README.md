# pretense-py

A lightweight stateful property-testing and behavioral contract framework.

## Overview

Pretense provides model-based state machine property testing, fuzz generation, and specification parity arbiters.

### Key Capabilities

- **State Machine Specification**: Declare states, transitions, preconditions, and invariants using `@transition`.
- **Fuzz Testing**: Deterministic state machine exploration powered by Hypothesis.
- **Contract Verification**: Parity and behavioral conformance testing between specifications and implementations.
- **Command Line Runner**: Run state machine suites across packages via `pretense <path>`.

## Installation

```bash
uv pip install pretense-py
```

## Quick Start

```python
import pretense

# Import core pretense primitives
from pretense import transition, TransitionContext, StateMachine
```

Or run test suites directly:

```bash
pretense parts/
```
