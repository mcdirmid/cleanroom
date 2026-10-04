#!/bin/bash
# high_lint_test.sh — tests for high_lint.py.
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

# Case 1: Valid interface HLS spec
mkdir -p "$tmp/c1"
cat > "$tmp/c1/my_service.md" <<'EOF'
# my_service

## Purpose
A service for handling data requests.

## Types and Behavior
Defines core data structures and behavior.
EOF
if python3 "$bin/high_lint.py" "$tmp/c1/my_service.md" >/dev/null 2>&1; then
    echo "PASS: c1 valid interface spec"
else
    echo "FAIL: c1 valid interface spec should pass" >&2
    fail=1
fi

# Case 2: Header mismatch error
mkdir -p "$tmp/c2"
cat > "$tmp/c2/wrong_name.md" <<'EOF'
# other_name

## Purpose
Some purpose.

## Types and Behavior
Some behavior.
EOF
if python3 "$bin/high_lint.py" "$tmp/c2/wrong_name.md" 2>"$tmp/c2/err.log"; then
    echo "FAIL: c2 header mismatch should fail" >&2
    fail=1
else
    check "c2 header mismatch error" "$tmp/c2/err.log" "header must be '# wrong_name'"
fi

# Case 3: Valid implementation HLS spec with implements:
mkdir -p "$tmp/c3"
cat > "$tmp/c3/my_service_impl.md" <<'EOF'
# my_service_impl
imports: my_service
implements: my_service

## Purpose
Implementation of my_service.

## Types and Behavior
Implements service logic.
EOF
if python3 "$bin/high_lint.py" "$tmp/c3/my_service_impl.md" >/dev/null 2>&1; then
    echo "PASS: c3 valid implementation spec"
else
    echo "FAIL: c3 valid implementation spec should pass" >&2
    fail=1
fi

# Case 4: Implementation missing implements:
mkdir -p "$tmp/c4"
cat > "$tmp/c4/bad_impl.md" <<'EOF'
# bad_impl
imports: my_service

## Purpose
Implementation of my_service.

## Types and Behavior
Implements service logic.
EOF
if python3 "$bin/high_lint.py" "$tmp/c4/bad_impl.md" 2>"$tmp/c4/err.log"; then
    echo "FAIL: c4 impl missing implements should fail" >&2
    fail=1
else
    check "c4 impl missing implements" "$tmp/c4/err.log" "implementation specification must declare 'implements: <type>'"
fi

# Case 5: Non-asm importing _impl
mkdir -p "$tmp/c5"
cat > "$tmp/c5/bad_interface.md" <<'EOF'
# bad_interface
imports: other_impl

## Purpose
Interface importing an impl.

## Types and Behavior
Invalid dependency.
EOF
if python3 "$bin/high_lint.py" "$tmp/c5/bad_interface.md" 2>"$tmp/c5/err.log"; then
    echo "FAIL: c5 non-asm importing _impl should fail" >&2
    fail=1
else
    check "c5 non-asm importing _impl" "$tmp/c5/err.log" "must not import implementation 'other_impl'"
fi

# Case 6: Unknown section
mkdir -p "$tmp/c6"
cat > "$tmp/c6/bad_section.md" <<'EOF'
# bad_section

## Purpose
Valid purpose.

## InvalidSection
Invalid heading.
EOF
if python3 "$bin/high_lint.py" "$tmp/c6/bad_section.md" 2>"$tmp/c6/err.log"; then
    echo "FAIL: c6 unknown section should fail" >&2
    fail=1
else
    check "c6 unknown section" "$tmp/c6/err.log" "unknown section '## InvalidSection'"
fi

exit "$fail"
