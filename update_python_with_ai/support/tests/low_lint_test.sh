#!/bin/bash
# low_lint_test.sh — tests for low_lint.py.
#
# Runs under a bazel test sandbox; the linter arrives via runfiles under
# $TEST_SRCDIR. Tests valid and invalid cases in temporary directory.

set -euo pipefail

if [ -n "${TEST_SRCDIR:-}" ]; then
    ws="${TEST_SRCDIR}/${TEST_WORKSPACE:-_main}"
    bin="$ws/update_python_with_ai/support/lib"
else
    bin="$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)"
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fail=0

check() { # check <desc> <file> <pattern>
    if grep -q "$3" "$2"; then
        echo "PASS: $1"
    else
        echo "FAIL: $1 (missing '$3' in $2)" >&2
        fail=1
    fi
}

# Case 1: Valid interface spec
mkdir -p "$tmp/c1"
cat > "$tmp/c1/my_service.pyi" <<'EOF'
from typing import Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier

@singleton_type("system")
class MyService(InTier[SystemTier], Protocol):
    """Manages active system records.

    INVARIANTS:
    - Service persists across system execution.
    """

    @operation
    def execute(self, payload: str) -> bool:
        """Executes operation with payload.

        PRECONDITIONS:
        - Payload is non-empty.

        POSTCONDITIONS:
        - MUST return True when execution succeeds.
        """
        ...
EOF
if python3 "$bin/low_lint.py" "$tmp/c1/my_service.pyi" >/dev/null 2>&1; then
    echo "PASS: c1 valid interface spec"
else
    echo "FAIL: c1 valid interface spec should pass" >&2
    fail=1
fi

# Case 2: Free-floating comment rejected
mkdir -p "$tmp/c2"
cat > "$tmp/c2/bad_comment.pyi" <<'EOF'
# This is a forbidden free-floating comment
from framework import singleton_type

@singleton_type
class Service:
    ...
EOF
if python3 "$bin/low_lint.py" "$tmp/c2/bad_comment.pyi" 2>"$tmp/c2/err.log"; then
    echo "FAIL: c2 free-floating comment should fail" >&2
    fail=1
else
    check "c2 free-floating comment" "$tmp/c2/err.log" "free-floating '#' comment prohibited"
fi

# Case 3: Prohibited docstring section rejected
mkdir -p "$tmp/c3"
cat > "$tmp/c3/prohibited_section.pyi" <<'EOF'
from framework import operation, singleton_type

@singleton_type
class Service:
    """Service description.

    REQUIREMENTS:
    - Must do something.
    """
    @operation
    def run(self) -> None:
        ...
EOF
if python3 "$bin/low_lint.py" "$tmp/c3/prohibited_section.pyi" 2>"$tmp/c3/err.log"; then
    echo "FAIL: c3 prohibited section should fail" >&2
    fail=1
else
    check "c3 prohibited section" "$tmp/c3/err.log" "prohibited docstring section 'REQUIREMENTS:'"
fi

# Case 4: Contract sentence missing period rejected
mkdir -p "$tmp/c4"
cat > "$tmp/c4/missing_period.pyi" <<'EOF'
from framework import operation, singleton_type

@singleton_type
class Service:
    """Service description.

    INVARIANTS:
    - Must end with period
    """
    @operation
    def run(self) -> None:
        ...
EOF
if python3 "$bin/low_lint.py" "$tmp/c4/missing_period.pyi" 2>"$tmp/c4/err.log"; then
    echo "FAIL: c4 missing period should fail" >&2
    fail=1
else
    check "c4 missing period" "$tmp/c4/err.log" "sentence under 'INVARIANTS:' must end with a period"
fi

# Case 5: Service method missing @property or @operation rejected
mkdir -p "$tmp/c5"
cat > "$tmp/c5/missing_dec.pyi" <<'EOF'
from framework import singleton_type

@singleton_type
class Service:
    def helper(self) -> None:
        ...
EOF
if python3 "$bin/low_lint.py" "$tmp/c5/missing_dec.pyi" 2>"$tmp/c5/err.log"; then
    echo "FAIL: c5 missing member decorator should fail" >&2
    fail=1
else
    check "c5 missing member decorator" "$tmp/c5/err.log" "must be decorated with either @property or @operation"
fi

# Case 6: Property taking extra arguments rejected
mkdir -p "$tmp/c6"
cat > "$tmp/c6/bad_property.pyi" <<'EOF'
from framework import singleton_type

@singleton_type
class Service:
    @property
    def value(self, extra: int) -> int:
        ...
EOF
if python3 "$bin/low_lint.py" "$tmp/c6/bad_property.pyi" 2>"$tmp/c6/err.log"; then
    echo "FAIL: c6 property with extra args should fail" >&2
    fail=1
else
    check "c6 property extra args" "$tmp/c6/err.log" "must take strictly 'self'"
fi

# Case 7: Type invariant repeated as precondition rejected
mkdir -p "$tmp/c7"
cat > "$tmp/c7/repeated_inv.pyi" <<'EOF'
from framework import operation, singleton_type

@singleton_type
class Service:
    """Service description.

    INVARIANTS:
    - Service is always active.
    """

    @operation
    def act(self) -> None:
        """Acts on service.

        PRECONDITIONS:
        - Service is always active.
        """
        ...
EOF
if python3 "$bin/low_lint.py" "$tmp/c7/repeated_inv.pyi" 2>"$tmp/c7/err.log"; then
    echo "FAIL: c7 repeated invariant should fail" >&2
    fail=1
else
    check "c7 repeated invariant" "$tmp/c7/err.log" "type invariant repeated as precondition"
fi

# Case 8: Valid assembly spec
mkdir -p "$tmp/c8"
cat > "$tmp/c8/sample_asm.pyi" <<'EOF'
"""Assembly module."""

def __initialize__() -> None:
    """Initializes assembly constituents.

    CONSTITUENTS:
    - constituent_impl
    """
    ...
EOF
if python3 "$bin/low_lint.py" "$tmp/c8/sample_asm.pyi" >/dev/null 2>&1; then
    echo "PASS: c8 valid assembly spec"
else
    echo "FAIL: c8 valid assembly spec should pass" >&2
    fail=1
fi

# Case 9: Valid external spec
mkdir -p "$tmp/c9"
cat > "$tmp/c9/sample_ext.pyi" <<'EOF'
"""
## External Mechanics & API Documentation

Details external mechanics.

## Build Dependencies

(none)

## Usage Snippets

```python
pass
```
"""
EOF
if python3 "$bin/low_lint.py" "$tmp/c9/sample_ext.pyi" >/dev/null 2>&1; then
    echo "PASS: c9 valid external spec"
else
    echo "FAIL: c9 valid external spec should pass" >&2
    fail=1
fi

exit "$fail"
