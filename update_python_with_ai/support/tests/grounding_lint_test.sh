#!/bin/bash
# grounding_lint_test.sh — tests for grounding_lint.py.
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

# Case 1: Valid grounding interface spec with proof statements and terminal raise
mkdir -p "$tmp/c1"
cat > "$tmp/c1/valid_service.py" <<'EOF'
from typing import Mapping, Protocol
from framework import operation, singleton_type
from support.lib.grounding_support import InTier, SystemTier

@singleton_type("system")
class MyService(InTier[SystemTier], Protocol):
    """Manages active system records."""

    @operation
    def execute(self, payload: str) -> bool:
        """Executes operation with payload.

        COVERED:
        - Must process non-empty payload.
        """
        # knowledge requirement covered: evaluate condition check
        _is_valid: bool = len(payload) > 0
        raise NotImplementedError

    @operation
    def deferred_op(self) -> int:
        """Abstract operation requiring backing state.

        DEFERRED:
        - Must provide backing count.
        """
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c1/valid_service.py" >/dev/null 2>&1; then
    echo "PASS: c1 valid grounding spec"
else
    echo "FAIL: c1 valid grounding spec should pass" >&2
    fail=1
fi

# Case 2: Prohibited if statement rejected
mkdir -p "$tmp/c2"
cat > "$tmp/c2/bad_if.py" <<'EOF'
class Service:
    def execute(self, x: int) -> bool:
        """
        COVERED:
        - Must check value.
        """
        if x > 0:
            val = True
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c2/bad_if.py" 2>"$tmp/c2/err.log"; then
    echo "FAIL: c2 if statement should fail" >&2
    fail=1
else
    check "c2 if statement" "$tmp/c2/err.log" "conditional statement 'if' is prohibited"
fi

# Case 3: Prohibited ternary if expression rejected
mkdir -p "$tmp/c3"
cat > "$tmp/c3/bad_ifexp.py" <<'EOF'
class Service:
    def execute(self, x: int) -> bool:
        """
        COVERED:
        - Must check value.
        """
        val: bool = True if x > 0 else False
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c3/bad_ifexp.py" 2>"$tmp/c3/err.log"; then
    echo "FAIL: c3 ternary if expression should fail" >&2
    fail=1
else
    check "c3 ternary if expression" "$tmp/c3/err.log" "conditional ternary expression '... if ... else ...' is prohibited"
fi

# Case 4: Prohibited return statement rejected
mkdir -p "$tmp/c4"
cat > "$tmp/c4/bad_return.py" <<'EOF'
class Service:
    def execute(self, x: int) -> bool:
        """
        COVERED:
        - Must check value.
        """
        val: bool = x > 0
        return val
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c4/bad_return.py" 2>"$tmp/c4/err.log"; then
    echo "FAIL: c4 return statement should fail" >&2
    fail=1
else
    check "c4 return statement" "$tmp/c4/err.log" "'return' statement is prohibited in grounding specifications"
fi

# Case 5: Prohibited ellipsis in method body rejected
mkdir -p "$tmp/c5"
cat > "$tmp/c5/bad_ellipsis.py" <<'EOF'
class Service:
    def execute(self, x: int) -> bool:
        """
        COVERED:
        - Must check value.
        """
        ...
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c5/bad_ellipsis.py" 2>"$tmp/c5/err.log"; then
    echo "FAIL: c5 ellipsis body should fail" >&2
    fail=1
else
    check "c5 ellipsis body" "$tmp/c5/err.log" "ellipsis '...' is prohibited in grounding specifications"
fi

# Case 6: Permitted ellipsis in type annotations
mkdir -p "$tmp/c6"
cat > "$tmp/c6/annotation_ellipsis.py" <<'EOF'
from typing import Callable, Tuple

class Service:
    def execute(self, cb: Callable[..., int]) -> Tuple[str, ...]:
        """
        COVERED:
        - Must call callback.
        """
        _fn: Callable[..., int] = cb
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c6/annotation_ellipsis.py" >/dev/null 2>&1; then
    echo "PASS: c6 ellipsis in type annotations allowed"
else
    echo "FAIL: c6 ellipsis in type annotations should pass" >&2
    fail=1
fi

# Case 7: Prohibited loop rejected
mkdir -p "$tmp/c7"
cat > "$tmp/c7/bad_loop.py" <<'EOF'
from typing import Sequence

class Service:
    def execute(self, items: Sequence[int]) -> None:
        """
        COVERED:
        - Must process items.
        """
        for item in items:
            _x = item
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c7/bad_loop.py" 2>"$tmp/c7/err.log"; then
    echo "FAIL: c7 loop should fail" >&2
    fail=1
else
    check "c7 loop" "$tmp/c7/err.log" "loop statement 'for' is prohibited"
fi

# Case 8: Prohibited try block rejected
mkdir -p "$tmp/c8"
cat > "$tmp/c8/bad_try.py" <<'EOF'
class Service:
    def execute(self, x: int) -> None:
        """
        COVERED:
        - Must handle errors.
        """
        try:
            _y = x
        except Exception:
            _y = 0
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c8/bad_try.py" 2>"$tmp/c8/err.log"; then
    echo "FAIL: c8 try block should fail" >&2
    fail=1
else
    check "c8 try block" "$tmp/c8/err.log" "'try' block is prohibited"
fi

# Case 9: Missing terminal raise rejected
mkdir -p "$tmp/c9"
cat > "$tmp/c9/missing_raise.py" <<'EOF'
class Service:
    def execute(self, x: int) -> int:
        """
        COVERED:
        - Must assign x.
        """
        _y: int = x
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c9/missing_raise.py" 2>"$tmp/c9/err.log"; then
    echo "FAIL: c9 missing terminal raise should fail" >&2
    fail=1
else
    check "c9 missing terminal raise" "$tmp/c9/err.log" "must terminate with 'raise NotImplementedError'"
fi

# Case 10: Wrong exception type rejected
mkdir -p "$tmp/c10"
cat > "$tmp/c10/wrong_raise.py" <<'EOF'
class Service:
    def execute(self, x: int) -> int:
        """
        COVERED:
        - Must assign x.
        """
        _y: int = x
        raise RuntimeError("failed")
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c10/wrong_raise.py" 2>"$tmp/c10/err.log"; then
    echo "FAIL: c10 wrong exception should fail" >&2
    fail=1
else
    check "c10 wrong exception" "$tmp/c10/err.log" "must raise 'NotImplementedError', not 'RuntimeError'"
fi

# Case 11: Unreachable dead code after terminal raise rejected
mkdir -p "$tmp/c11"
cat > "$tmp/c11/dead_code.py" <<'EOF'
class Service:
    def execute(self, x: int) -> int:
        """
        COVERED:
        - Must assign x.
        """
        _y: int = x
        raise NotImplementedError
        _z: int = 1
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c11/dead_code.py" 2>"$tmp/c11/err.log"; then
    echo "FAIL: c11 dead code after raise should fail" >&2
    fail=1
else
    check "c11 dead code after raise" "$tmp/c11/err.log" "early 'raise' statement is prohibited"
fi

# Case 12: Direct self-recursion rejected
mkdir -p "$tmp/c12"
cat > "$tmp/c12/self_recurse.py" <<'EOF'
class Service:
    def execute(self, x: int) -> int:
        """
        COVERED:
        - Must compute value.
        """
        _y: int = self.execute(x)
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c12/self_recurse.py" 2>"$tmp/c12/err.log"; then
    echo "FAIL: c12 self recursion should fail" >&2
    fail=1
else
    check "c12 self recursion" "$tmp/c12/err.log" "direct self-recursion 'self.execute(...)' is prohibited"
fi

# Case 13: Claiming COVERED: with bare raise rejected
mkdir -p "$tmp/c13"
cat > "$tmp/c13/bare_covered.py" <<'EOF'
class Service:
    def execute(self, x: int) -> int:
        """
        COVERED:
        - Must compute value.
        """
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c13/bare_covered.py" 2>"$tmp/c13/err.log"; then
    echo "FAIL: c13 bare covered should fail" >&2
    fail=1
else
    check "c13 bare covered" "$tmp/c13/err.log" "claims 'COVERED:' but has no proof statements before 'raise NotImplementedError'"
fi

# Case 14: Abstract method with DEFERRED: and bare raise passes
mkdir -p "$tmp/c14"
cat > "$tmp/c14/deferred_op.py" <<'EOF'
class Service:
    def execute(self, x: int) -> int:
        """
        DEFERRED:
        - Must compute value in subtype.
        """
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c14/deferred_op.py" >/dev/null 2>&1; then
    echo "PASS: c14 deferred op with bare raise passes"
else
    echo "FAIL: c14 deferred op with bare raise should pass" >&2
    fail=1
fi

# Case 15: Prohibited docstring section rejected
mkdir -p "$tmp/c15"
cat > "$tmp/c15/prohibited_section.py" <<'EOF'
class Service:
    def execute(self, x: int) -> int:
        """
        REQUIREMENTS:
        - Must compute value.
        """
        _y: int = x
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c15/prohibited_section.py" 2>"$tmp/c15/err.log"; then
    echo "FAIL: c15 prohibited section should fail" >&2
    fail=1
else
    check "c15 prohibited section" "$tmp/c15/err.log" "prohibited docstring section 'REQUIREMENTS:'"
fi

# Case 16: Sentence missing period rejected
mkdir -p "$tmp/c16"
cat > "$tmp/c16/missing_period.py" <<'EOF'
class Service:
    def execute(self, x: int) -> int:
        """
        COVERED:
        - Must compute value
        """
        _y: int = x
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c16/missing_period.py" 2>"$tmp/c16/err.log"; then
    echo "FAIL: c16 missing period should fail" >&2
    fail=1
else
    check "c16 missing period" "$tmp/c16/err.log" "sentence under 'COVERED:' must end with a period"
fi

# Case 17: Valid assembly spec passes
mkdir -p "$tmp/c17"
cat > "$tmp/c17/sample_asm.py" <<'EOF'
"""Assembly module."""

def __initialize__() -> None:
    """Initializes constituents.

    CONSTITUENTS:
    - dep_impl
    """
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c17/sample_asm.py" >/dev/null 2>&1; then
    echo "PASS: c17 valid assembly spec passes"
else
    echo "FAIL: c17 valid assembly spec should pass" >&2
    fail=1
fi

# Case 18: Comments with 'if' allowed
mkdir -p "$tmp/c18"
cat > "$tmp/c18/if_comment.py" <<'EOF'
class Service:
    def execute(self, x: int) -> int:
        """
        COVERED:
        - Must evaluate check.
        """
        # Check if x is positive and assign condition knowledge
        _cond: bool = x > 0
        raise NotImplementedError
EOF
if python3 "$bin/grounding_lint.py" "$tmp/c18/if_comment.py" >/dev/null 2>&1; then
    echo "PASS: c18 comments with 'if' allowed"
else
    echo "FAIL: c18 comments with 'if' should pass" >&2
    fail=1
fi

exit "$fail"
