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

# Case 6: non-relative sibling import -> rewritten to relative syntax and accepted.
mkdir -p "$tmp/c6/lib"
cat > "$tmp/c6/lib/sibling.py" <<'EOF'
class Sibling:
    pass
EOF
cat > "$tmp/c6/lib/main.py" <<'EOF'
from sibling import Sibling
EOF
if ( cd "$tmp/c6" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/main.py ); then
    echo "PASS: c6 rewrote and accepted non-relative sibling import"
else
    echo "FAIL: c6 expected success after rewriting non-relative sibling import" >&2
    fail=1
fi
check "c6 rewritten to relative" "$tmp/c6/lib/main.py" 'from \.sibling import Sibling'


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

# Case 15: Implementation class named with 'Impl' suffix -> rejected with mismatch against spec.
mkdir -p "$tmp/c15/lib" "$tmp/c15/specs/grounding"
cat > "$tmp/c15/specs/grounding/widget_impl.pyi" <<'EOF'
class Widget:
    ...
EOF
cat > "$tmp/c15/lib/widget_impl.py" <<'EOF'
class WidgetImpl:
    pass
EOF
if ( cd "$tmp/c15" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/widget_impl.py 2>"$tmp/c15/err.log" ); then
    echo "FAIL: c15 expected failure when implementation class has Impl suffix" >&2
    fail=1
else
    if grep -q "public type 'WidgetImpl' is defined in library code but is not declared in grounding specification" "$tmp/c15/err.log" && \
       grep -q "type 'Widget' declared in grounding specification 'widget_impl.pyi' is not defined in library code" "$tmp/c15/err.log"; then
        echo "PASS: c15 rejected WidgetImpl and required Widget from specification"
    else
        echo "FAIL: c15 did not report expected public type mismatch errors" >&2
        fail=1
    fi
fi

# Case 16: Extra public helper class without preceding underscore -> rejected with error.
mkdir -p "$tmp/c16/lib" "$tmp/c16/specs/grounding"
cat > "$tmp/c16/specs/grounding/service_impl.pyi" <<'EOF'
class Service:
    ...
EOF
cat > "$tmp/c16/lib/service_impl.py" <<'EOF'
class Service:
    pass

class Helper:
    pass
EOF
if ( cd "$tmp/c16" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/service_impl.py 2>"$tmp/c16/err.log" ); then
    echo "FAIL: c16 expected failure when helper class lacks preceding underscore" >&2
    fail=1
else
    if grep -q "public type 'Helper' is defined in library code but is not declared in grounding specification" "$tmp/c16/err.log"; then
        echo "PASS: c16 rejected public helper class without underscore"
    else
        echo "FAIL: c16 did not report missing underscore error for helper class" >&2
        fail=1
    fi
fi

# Case 17: Helper class with preceding underscore and referenced -> passes cleanly.
mkdir -p "$tmp/c17/lib" "$tmp/c17/specs/grounding"
cat > "$tmp/c17/specs/grounding/clean_impl.pyi" <<'EOF'
class CleanService:
    ...
EOF
cat > "$tmp/c17/lib/clean_impl.py" <<'EOF'
class _InternalHelper:
    pass

class CleanService:
    _helper = _InternalHelper
EOF
if ( cd "$tmp/c17" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/clean_impl.py 2>"$tmp/c17/err.log" ); then
    echo "PASS: c17 accepted helper class with preceding underscore"
else
    echo "FAIL: c17 failed unexpectedly on helper class with preceding underscore" >&2
    cat "$tmp/c17/err.log" >&2
    fail=1
fi

# Case 18: Unused private helper function -> rejected with dead code error.
mkdir -p "$tmp/c18/lib" "$tmp/c18/specs/grounding"
cat > "$tmp/c18/specs/grounding/service_impl.pyi" <<'EOF'
class Service:
    ...
EOF
cat > "$tmp/c18/lib/service_impl.py" <<'EOF'
class Service:
    pass

def _unused_helper():
    pass
EOF
if ( cd "$tmp/c18" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/service_impl.py 2>"$tmp/c18/err.log" ); then
    echo "FAIL: c18 expected failure when private function is unreferenced" >&2
    fail=1
else
    if grep -q "private function '_unused_helper' is defined in library code but never referenced (dead code)" "$tmp/c18/err.log"; then
        echo "PASS: c18 rejected unused private function as dead code"
    else
        echo "FAIL: c18 did not report dead code error for unused private function" >&2
        cat "$tmp/c18/err.log" >&2
        fail=1
    fi
fi

# Case 19: cross-part import -> rewritten to full package path and added to pyright_deps.
mkdir -p "$tmp/c19/lib"
cat > "$tmp/c19/lib/consumer.py" <<'EOF'
from dag_storage import DagStorage

class Consumer:
    def __init__(self, s: DagStorage) -> None:
        self.s = s
EOF
if ( cd "$tmp/c19" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/consumer.py --deps //update_with_ai/parts/dag/lib:dag_storage ); then
    echo "PASS: c19 accepted and rewrote cross-part import"
else
    echo "FAIL: c19 expected success with cross-part import rewriting" >&2
    fail=1
fi
check "c19 rewritten import" "$tmp/c19/lib/consumer.py" 'from update_with_ai\.parts\.dag\.lib\.dag_storage import DagStorage'
check "c19 dep in BUILD" "$tmp/c19/lib/BUILD.bazel" '"//update_with_ai/parts/dag/lib:dag_storage"'

# Case 20: lifecycle import -> rewritten to support.lib.lifecycle.
mkdir -p "$tmp/c20/lib"
cat > "$tmp/c20/lib/init_module.py" <<'EOF'
from lifecycle import LifecycleRegistry

def __initialize__(registry: LifecycleRegistry) -> None:
    pass
EOF
if ( cd "$tmp/c20" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/init_module.py ); then
    echo "PASS: c20 accepted and rewrote lifecycle import"
else
    echo "FAIL: c20 expected success with lifecycle import rewriting" >&2
    fail=1
fi
check "c20 rewritten lifecycle" "$tmp/c20/lib/init_module.py" 'from support\.lib\.lifecycle import LifecycleRegistry'

# Case 21: grounding imports rewritten to lib, DO NOT EDIT markers and _ext imports stripped.
mkdir -p "$tmp/c21/lib"
cat > "$tmp/c21/lib/consumer.py" <<'EOF'
# --- DO NOT EDIT: Auto-generated dependencies ---
from update_with_ai.parts.dag.grounding.dag_storage import DagStorage
import dummy_ext
# --- END DO NOT EDIT ---

class Consumer:
    def __init__(self, s: DagStorage) -> None:
        self.s = s
EOF
if ( cd "$tmp/c21" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/consumer.py --deps //update_with_ai/parts/dag/lib:dag_storage,tool_provider ); then
    echo "PASS: c21 lint succeeded"
else
    echo "FAIL: c21 expected success linting consumer" >&2
    fail=1
fi
if grep -q 'DO NOT EDIT' "$tmp/c21/lib/consumer.py"; then
    echo "FAIL: c21 DO NOT EDIT markers not stripped" >&2
    fail=1
else
    echo "PASS: c21 DO NOT EDIT markers stripped"
fi
if grep -q 'dummy_ext' "$tmp/c21/lib/consumer.py"; then
    echo "FAIL: c21 _ext import not stripped" >&2
    fail=1
else
    echo "PASS: c21 _ext import stripped"
fi
check "c21 rewritten to lib" "$tmp/c21/lib/consumer.py" 'from update_with_ai\.parts\.dag\.lib\.dag_storage import DagStorage'
if grep -q '# Dependencies:' "$tmp/c21/lib/consumer.py"; then
    echo "FAIL: c21 unexpected dependency comment line" >&2
    fail=1
else
    echo "PASS: c21 no dependency comment line present"
fi

# Case 22: undeclared dependency import fails with diagnostic listing allowed dependencies.
mkdir -p "$tmp/c22/lib"
cat > "$tmp/c22/lib/bad_import.py" <<'EOF'
import unauthorized_lib

class Bad:
    pass
EOF
if ( cd "$tmp/c22" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/bad_import.py --deps tool_provider 2>"$tmp/c22/err.log" ); then
    echo "FAIL: c22 expected failure on undeclared import" >&2
    fail=1
else
    echo "PASS: c22 rejected undeclared import"
fi
check "c22 undeclared error diagnostic" "$tmp/c22/err.log" "undeclared dependency 'unauthorized_lib'. Allowed dependencies: tool_provider"

# Case 23: empty module with .pyi spec -> scaffolded with valid skeleton and TODO bodies.
mkdir -p "$tmp/c23/lib" "$tmp/c23/grounding"
cat > "$tmp/c23/grounding/worker_impl.pyi" <<'EOF'
from framework import operation, singleton_type

@singleton_type('agent_session')
class Worker:
    @operation
    def process_item(self, item: str) -> bool:
        ...
EOF
touch "$tmp/c23/lib/worker_impl.py"
if ( cd "$tmp/c23" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/worker_impl.py --pyi "$tmp/c23/grounding/worker_impl.pyi" ); then
    echo "PASS: c23 auto-generated skeleton from .pyi"
else
    echo "FAIL: c23 failed to generate skeleton from .pyi" >&2
    fail=1
fi
check "c23 spec reference header" "$tmp/c23/lib/worker_impl.py" '# Requirements specified in worker_impl.pyi'
check "c23 class skeleton" "$tmp/c23/lib/worker_impl.py" 'class Worker(Singleton):'
check "c23 tier" "$tmp/c23/lib/worker_impl.py" 'tier = agent_session'
check "c23 init todo" "$tmp/c23/lib/worker_impl.py" '# TODO___init___body'
check "c23 method todo" "$tmp/c23/lib/worker_impl.py" '# TODO_process_item_body'
check "c23 initialize" "$tmp/c23/lib/worker_impl.py" 'def __initialize__(registry: Optional\[LifecycleRegistry\] = None) -> None:'
check "c23 register singleton" "$tmp/c23/lib/worker_impl.py" 'reg.register_singleton('

# Case 24: module containing uninitialized <TargetClass> placeholder -> replaced with skeleton.
mkdir -p "$tmp/c24/lib" "$tmp/c24/grounding"
cat > "$tmp/c24/grounding/service.pyi" <<'EOF'
from typing import Protocol
from framework import poly_type

@poly_type
class Service(Protocol):
    def serve(self) -> str:
        ...
EOF
cat > "$tmp/c24/lib/service.py" <<'EOF'
class <TargetClass>(Protocol):
    pass
EOF
if ( cd "$tmp/c24" && python3 "$bin/lib_lint.py" lib/BUILD.bazel lib/service.py --pyi "$tmp/c24/grounding/service.pyi" ); then
    echo "PASS: c24 replaced <TargetClass> with valid skeleton"
else
    echo "FAIL: c24 failed to replace <TargetClass>" >&2
    fail=1
fi
check "c24 spec reference header" "$tmp/c24/lib/service.py" '# Requirements specified in service.pyi'
check "c24 protocol class" "$tmp/c24/lib/service.py" 'class Service(Protocol):'
check "c24 method todo" "$tmp/c24/lib/service.py" '# TODO_serve_body'

exit "$fail"
