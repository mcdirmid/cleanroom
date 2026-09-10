#!/bin/bash
# lib_lint_test.sh — gate: lib_lint.py creates/fixes pyright_library entries.
#
# Runs under a bazel test sandbox; the linter arrives via runfiles under
# $TEST_SRCDIR. Each case builds fixture BUILD files in a temp dir, runs the
# linter from inside the case dir (so labels are package-relative), and
# asserts the fixed output.

set -euo pipefail

ws="${TEST_SRCDIR}/${TEST_WORKSPACE:-_main}"
if [ ! -d "$ws" ]; then
    echo "runfiles workspace not found at $ws" >&2
    exit 1
fi
bin="$ws/update_with_ai/support/lib"

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

# Case 1: BUILD.bazel missing -> created with load + target + deps.
mkdir -p "$tmp/c1/lib"
(
    cd "$tmp/c1"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/module1.py --deps dag_storage,tool_provider
)
check "c1 load" "$tmp/c1/lib/BUILD.bazel" 'load("//bin:pyright_library.bzl", "pyright_library")'
check "c1 target" "$tmp/c1/lib/BUILD.bazel" 'name = "module1"'
check "c1 srcs" "$tmp/c1/lib/BUILD.bazel" 'srcs = \["module1.py"\]'
check "c1 dep1" "$tmp/c1/lib/BUILD.bazel" '"//lib:dag_storage"'
check "c1 dep2" "$tmp/c1/lib/BUILD.bazel" '"//lib:tool_provider"'
check "c1 deps" "$tmp/c1/lib/BUILD.bazel" 'deps = \[\]'
check "c1 visibility" "$tmp/c1/lib/BUILD.bazel" 'visibility = \["//visibility:public"\]'

# Case 2: load missing -> added; existing target untouched.
mkdir -p "$tmp/c2/lib"
cat > "$tmp/c2/lib/BUILD.bazel" <<'EOF'
pyright_library(
    name = "module2",
    srcs = ["module2.py"],
    pyright_deps = [],
    deps = [],
    visibility = ["//visibility:public"],
)
EOF
(
    cd "$tmp/c2"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/module2.py --deps dag_storage
)
check "c2 load added" "$tmp/c2/lib/BUILD.bazel" 'load("//bin:pyright_library.bzl", "pyright_library")'
check "c2 dep added" "$tmp/c2/lib/BUILD.bazel" '"//lib:dag_storage"'
check "c2 target kept" "$tmp/c2/lib/BUILD.bazel" 'name = "module2"'

# Case 3: target missing -> added; existing targets untouched.
mkdir -p "$tmp/c3/lib"
cat > "$tmp/c3/lib/BUILD.bazel" <<'EOF'
load("//bin:pyright_library.bzl", "pyright_library")
pyright_library(
    name = "other",
    srcs = ["other.py"],
    pyright_deps = [],
    deps = [],
    visibility = ["//visibility:public"],
)
EOF
(
    cd "$tmp/c3"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/module3.py --deps tool_provider
)
check "c3 target added" "$tmp/c3/lib/BUILD.bazel" 'name = "module3"'
check "c3 dep" "$tmp/c3/lib/BUILD.bazel" '"//lib:tool_provider"'
check "c3 existing kept" "$tmp/c3/lib/BUILD.bazel" 'name = "other"'

# Case 4: existing target with an extra dep -> missing dep added, extra kept.
mkdir -p "$tmp/c4/lib"
cat > "$tmp/c4/lib/BUILD.bazel" <<'EOF'
load("//bin:pyright_library.bzl", "pyright_library")
pyright_library(
    name = "module4",
    srcs = ["module4.py"],
    pyright_deps = ["//lib:extra"],
    deps = [],
    visibility = ["//visibility:public"],
)
EOF
(
    cd "$tmp/c4"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/module4.py --deps dag_storage
)
check "c4 dep added" "$tmp/c4/lib/BUILD.bazel" '"//lib:dag_storage"'
check "c4 extra kept" "$tmp/c4/lib/BUILD.bazel" '"//lib:extra"'

# Case 5: no --deps (empty module deps) -> target created with empty deps.
mkdir -p "$tmp/c5/lib"
(
    cd "$tmp/c5"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/module5.py
)
check "c5 target" "$tmp/c5/lib/BUILD.bazel" 'name = "module5"'
check "c5 empty deps" "$tmp/c5/lib/BUILD.bazel" 'pyright_deps = \[\]'

# Case 6: non-relative sibling import -> rejected with error.
mkdir -p "$tmp/c6/lib"
cat > "$tmp/c6/lib/sibling.py" <<'EOF'
class Sibling:
    pass
EOF
cat > "$tmp/c6/lib/main.py" <<'EOF'
from sibling import Sibling
EOF
if ( cd "$tmp/c6" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/main.py 2>/dev/null ); then
    echo "FAIL: c6 expected failure when sibling imported without dot" >&2
    fail=1
else
    echo "PASS: c6 rejected non-relative sibling import"
fi

# Case 7: relative sibling import -> accepted.
mkdir -p "$tmp/c7/lib"
cat > "$tmp/c7/lib/sibling.py" <<'EOF'
class Sibling:
    pass
EOF
cat > "$tmp/c7/lib/main.py" <<'EOF'
from .sibling import Sibling
EOF
if ( cd "$tmp/c7" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/main.py ); then
    echo "PASS: c7 accepted relative sibling import"
else
    echo "FAIL: c7 expected success with relative sibling import" >&2
    fail=1
fi

# Case 8: unittest.main() in library module -> rejected with error.
mkdir -p "$tmp/c8/lib"
cat > "$tmp/c8/lib/main.py" <<'EOF'
import unittest

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c8" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/main.py 2>/dev/null ); then
    echo "FAIL: c8 expected failure when unittest.main present in library module" >&2
    fail=1
else
    echo "PASS: c8 rejected unittest.main in library module"
fi

# Case 9: External spec with requirement("openai") -> deps populated and pip load added.
mkdir -p "$tmp/c9/lib" "$tmp/c9/specs"
cat > "$tmp/c9/specs/openai_ext.pyi" <<'EOF'
'''
## External Mechanics & API Documentation
## Build Dependencies

- `requirement("openai")`

## Usage Snippets
'''
EOF
(
    cd "$tmp/c9"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/agent_runner_impl.py --deps agent_runner,openai_ext --pyi-deps specs/openai_ext.pyi
)
check "c9 pip load added" "$tmp/c9/lib/BUILD.bazel" 'load("@pip//:requirements.bzl", "requirement")'
check "c9 pyright load" "$tmp/c9/lib/BUILD.bazel" 'load("//bin:pyright_library.bzl", "pyright_library")'
check "c9 target" "$tmp/c9/lib/BUILD.bazel" 'name = "agent_runner_impl"'
check "c9 requirement in deps" "$tmp/c9/lib/BUILD.bazel" 'requirement("openai")'
check "c9 lib dep in pyright_deps" "$tmp/c9/lib/BUILD.bazel" '"//lib:agent_runner"'
if grep -q "openai_ext" "$tmp/c9/lib/BUILD.bazel"; then
    echo "FAIL: c9 openai_ext should not be in pyright_deps" >&2
    fail=1
else
    echo "PASS: c9 openai_ext excluded from pyright_deps"
fi

# Case 10: Idempotency with existing requirement("openai") in deps -> preserved without clobbering.
(
    cd "$tmp/c9"
    python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/agent_runner_impl.py --deps agent_runner,openai_ext --pyi-deps specs/openai_ext.pyi
)
check "c10 requirement kept" "$tmp/c9/lib/BUILD.bazel" 'requirement("openai")'
# Count occurrences of requirement("openai") to ensure no duplicates
req_count=$(grep -c 'requirement("openai")' "$tmp/c9/lib/BUILD.bazel" || true)
if [ "$req_count" -eq 1 ]; then
    echo "PASS: c10 exactly one requirement in deps"
else
    echo "FAIL: c10 expected 1 requirement entry, found $req_count" >&2
    fail=1
fi

# Case 11: Syntax error in module -> lib_lint fails with code 1 and outputs error.
mkdir -p "$tmp/c11/lib"
cat > "$tmp/c11/lib/syntax_err.py" <<'EOF'
def broken(
EOF
if ( cd "$tmp/c11" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/syntax_err.py 2>"$tmp/c11/err.log" ); then
    echo "FAIL: c11 expected failure when syntax error present" >&2
    fail=1
else
    if grep -q "syntax error" "$tmp/c11/err.log"; then
        echo "PASS: c11 rejected module with syntax error and printed error"
    else
        echo "FAIL: c11 did not report syntax error in err.log" >&2
        fail=1
    fi
fi

# Case 12: Framework import in module -> rejected with error.
mkdir -p "$tmp/c12/lib"
cat > "$tmp/c12/lib/main.py" <<'EOF'
import framework

class Service:
    pass
EOF
if ( cd "$tmp/c12" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/main.py 2>"$tmp/c12/err.log" ); then
    echo "FAIL: c12 expected failure when framework imported" >&2
    fail=1
else
    if grep -q "library module must not import from 'framework'" "$tmp/c12/err.log"; then
        echo "PASS: c12 rejected import from framework"
    else
        echo "FAIL: c12 did not report framework import error" >&2
        fail=1
    fi
fi

# Case 13: Framework decorators used without importing framework -> rejected with error.
mkdir -p "$tmp/c13/lib"
cat > "$tmp/c13/lib/main.py" <<'EOF'
@singleton_type("system")
class Service:
    @operation
    def run(self) -> None:
        pass
EOF
if ( cd "$tmp/c13" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/main.py 2>"$tmp/c13/err.log" ); then
    echo "FAIL: c13 expected failure when framework decorators used" >&2
    fail=1
else
    if grep -q "specification framework decorator '@singleton_type' must not be used" "$tmp/c13/err.log" && \
       grep -q "specification framework decorator '@operation' must not be used" "$tmp/c13/err.log"; then
        echo "PASS: c13 rejected framework decorators used without framework import"
    else
        echo "FAIL: c13 did not report expected framework decorator errors" >&2
        fail=1
    fi
# Case 14: '# type: ignore' in library module -> rejected with error.
mkdir -p "$tmp/c14/lib"
cat > "$tmp/c14/lib/main.py" <<'EOF'
def compute(x: int) -> int:
    return x  # type: ignore[return-value]
EOF
if ( cd "$tmp/c14" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/main.py 2>"$tmp/c14/err.log" ); then
    echo "FAIL: c14 expected failure when '# type: ignore' used" >&2
    fail=1
else
    if grep -q "'# type: ignore' is prohibited" "$tmp/c14/err.log"; then
        echo "PASS: c14 rejected '# type: ignore' in library module"
    else
        echo "FAIL: c14 did not report type: ignore error" >&2
        fail=1
    fi
fi

exit "$fail"
