#!/bin/bash
# test_lint_test.sh — gate: test_lint.py creates/fixes pyright_test entries.

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

# Case 1: BUILD.bazel missing -> created with pyright_test target + deps
# (impl under test plus its spec deps).
mkdir -p "$tmp/c1/tests"
(
    cd "$tmp/c1"
    python3 "$bin/test_lint.py" tests/BUILD.bazel tests/dag_cleaner_impl_test.py --lib-pkg lib --deps dag_cleaner_impl,dag_storage,tool_provider
)
check "c1 load" "$tmp/c1/tests/BUILD.bazel" 'load("//bin:pyright_library.bzl", "pyright_test")'
check "c1 rule" "$tmp/c1/tests/BUILD.bazel" 'pyright_test('
check "c1 target" "$tmp/c1/tests/BUILD.bazel" 'name = "dag_cleaner_impl_test"'
check "c1 srcs" "$tmp/c1/tests/BUILD.bazel" 'srcs = \["dag_cleaner_impl_test.py"\]'
check "c1 dep impl" "$tmp/c1/tests/BUILD.bazel" '"//lib:dag_cleaner_impl"'
check "c1 dep iface" "$tmp/c1/tests/BUILD.bazel" '"//lib:dag_storage"'

# Case 2: existing target with partial deps -> missing added, existing kept.
mkdir -p "$tmp/c2/tests"
cat > "$tmp/c2/tests/BUILD.bazel" <<'EOF'
load("//bin:pyright_library.bzl", "pyright_library")
pyright_test(
    name = "sandbox_impl_test",
    srcs = ["sandbox_impl_test.py"],
    pyright_deps = ["//lib:sandbox_impl"],
    deps = [],
    visibility = ["//visibility:public"],
)
EOF
(
    cd "$tmp/c2"
    python3 "$bin/test_lint.py" tests/BUILD.bazel tests/sandbox_impl_test.py --lib-pkg lib --deps sandbox_impl,sandbox,agent_loop
)
check "c2 dep added" "$tmp/c2/tests/BUILD.bazel" '"//lib:sandbox"'
check "c2 dep kept" "$tmp/c2/tests/BUILD.bazel" '"//lib:sandbox_impl"'

# Case 3: test file exists but lacks unittest.main() -> fails
mkdir -p "$tmp/c3/tests"
cat > "$tmp/c3/tests/foo_test.py" <<'EOF'
import unittest
class FooTest(unittest.TestCase):
    def test_foo(self):
        pass
EOF
if ( cd "$tmp/c3" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c3 expected failure when unittest.main() missing" >&2
    fail=1
else
    echo "PASS: c3 rejected test file missing unittest.main()"
fi

# Case 4: test file exists with unittest.main() -> passes
mkdir -p "$tmp/c4/tests"
cat > "$tmp/c4/tests/foo_test.py" <<'EOF'
import unittest
class FooTest(unittest.TestCase):
    def test_foo(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c4" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib ); then
    echo "PASS: c4 accepted test file with unittest.main()"
else
    echo "FAIL: c4 expected success with unittest.main()" >&2
    fail=1
fi

# Case 5: test file imports lib module with package prefix -> fails
mkdir -p "$tmp/c5/lib" "$tmp/c5/tests"
cat > "$tmp/c5/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c5/tests/foo_test.py" <<'EOF'
import unittest
from update_with_ai.lib.foo import Foo
class FooTest(unittest.TestCase):
    def test_foo(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c5" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c5 expected failure when lib module imported with package prefix" >&2
    fail=1
else
    echo "PASS: c5 rejected test with package-prefixed lib import"
fi

# Case 6: test file imports lib module via lib.<name> -> passes
mkdir -p "$tmp/c6/lib" "$tmp/c6/tests"
cat > "$tmp/c6/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c6/tests/foo_test.py" <<'EOF'
import unittest
from lib.foo import Foo
class FooTest(unittest.TestCase):
    def test_foo(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c6" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib ); then
    echo "PASS: c6 accepted test with lib.<name> import"
else
    echo "FAIL: c6 expected success with lib.<name> import" >&2
    fail=1
fi

# Case 7: test file patches stdlib module directly -> fails
mkdir -p "$tmp/c7/lib" "$tmp/c7/tests"
cat > "$tmp/c7/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c7/tests/foo_test.py" <<'EOF'
import unittest
from unittest.mock import patch
from lib.foo import Foo
class FooTest(unittest.TestCase):
    @patch('os.path.isfile', return_value=True)
    def test_foo(self, mock_isfile):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c7" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c7 expected failure when patching os.path.isfile directly" >&2
    fail=1
else
    echo "PASS: c7 rejected direct stdlib patch"
fi

# Case 8: test file patches lib module and builtins -> passes
mkdir -p "$tmp/c8/lib" "$tmp/c8/tests"
cat > "$tmp/c8/lib/foo.py" <<'EOF'
import os
class Foo:
    pass
EOF
cat > "$tmp/c8/tests/foo_test.py" <<'EOF'
import unittest
from unittest.mock import patch, mock_open
from lib.foo import Foo
class FooTest(unittest.TestCase):
    @patch('lib.foo.os.path.isfile', return_value=True)
    def test_foo(self, mock_isfile):
        with patch('builtins.open', mock_open(read_data="data")):
            pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c8" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib ); then
    echo "PASS: c8 accepted lib and builtins patch targets"
else
    echo "FAIL: c8 expected success with lib and builtins patch targets" >&2
    fail=1
fi

# Case 9: @patch decorator without matching function parameter -> fails
mkdir -p "$tmp/c9/lib" "$tmp/c9/tests"
cat > "$tmp/c9/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c9/tests/foo_test.py" <<'EOF'
import unittest
from unittest.mock import patch
from lib.foo import Foo
class FooTest(unittest.TestCase):
    @patch('lib.foo.Foo')
    def test_foo(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c9" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c9 expected failure on @patch without matching parameter" >&2
    fail=1
else
    echo "PASS: c9 rejected @patch without matching parameter"
fi

# Case 10: test file defines no test methods -> fails
mkdir -p "$tmp/c10/lib" "$tmp/c10/tests"
cat > "$tmp/c10/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c10/tests/foo_test.py" <<'EOF'
import unittest
from lib.foo import Foo
class FooTest(unittest.TestCase):
    def helper_not_a_test(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c10" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c10 expected failure on test module with no test methods" >&2
    fail=1
else
    echo "PASS: c10 rejected test module with 0 test methods"
fi

# Case 11: dry-run test collection fails on broken import -> fails
mkdir -p "$tmp/c11/lib" "$tmp/c11/tests"
cat > "$tmp/c11/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c11/tests/foo_test.py" <<'EOF'
import unittest
import non_existent_package_that_fails_import
from lib.foo import Foo
class FooTest(unittest.TestCase):
    def test_foo(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c11" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>/dev/null ); then
    echo "FAIL: c11 expected failure on non-existent package import in dry-run" >&2
    fail=1
else
    echo "PASS: c11 rejected test with broken import in dry-run"
fi

# Case 12: test imports class with Impl suffix -> rejected
mkdir -p "$tmp/c12/lib" "$tmp/c12/tests"
cat > "$tmp/c12/lib/widget_impl.py" <<'EOF'
class Widget:
    pass
EOF
cat > "$tmp/c12/tests/widget_impl_test.py" <<'EOF'
import unittest
from lib.widget_impl import WidgetImpl
class WidgetTest(unittest.TestCase):
    def test_basic(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c12" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/widget_impl_test.py --lib-pkg lib 2>"$tmp/c12/err.log" ); then
    echo "FAIL: c12 expected failure when test imports class with Impl suffix" >&2
    fail=1
else
    if grep -q "implementation classes do not use an 'Impl' suffix; import 'Widget' instead of 'WidgetImpl'" "$tmp/c12/err.log"; then
        echo "PASS: c12 rejected import with Impl suffix and guided to Widget"
    else
        echo "FAIL: c12 did not report expected Impl suffix error" >&2
        fail=1
    fi
fi

# Case 13: test defines Mock<Target> class -> rejected
mkdir -p "$tmp/c13/lib" "$tmp/c13/tests"
cat > "$tmp/c13/lib/widget_impl.py" <<'EOF'
class Widget:
    pass
EOF
cat > "$tmp/c13/tests/widget_impl_test.py" <<'EOF'
import unittest
from lib.widget_impl import Widget
class MockWidget:
    pass
class WidgetTest(unittest.TestCase):
    def test_basic(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c13" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/widget_impl_test.py --lib-pkg lib 2>"$tmp/c13/err.log" ); then
    echo "FAIL: c13 expected failure when test defines MockWidget" >&2
    fail=1
else
    if grep -q "class under test 'Widget' must never be mocked" "$tmp/c13/err.log"; then
        echo "PASS: c13 rejected MockWidget definition"
    else
        echo "FAIL: c13 did not report expected MockWidget error" >&2
        fail=1
    fi
fi

# Case 14: test redefines class under test -> rejected
mkdir -p "$tmp/c14/lib" "$tmp/c14/tests"
cat > "$tmp/c14/lib/widget_impl.py" <<'EOF'
class Widget:
    pass
EOF
cat > "$tmp/c14/tests/widget_impl_test.py" <<'EOF'
import unittest
class Widget:
    pass
class WidgetTest(unittest.TestCase):
    def test_basic(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c14" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/widget_impl_test.py --lib-pkg lib 2>"$tmp/c14/err.log" ); then
    echo "FAIL: c14 expected failure when test redefines Widget class" >&2
    fail=1
else
    if grep -q "test module must not define class 'Widget' under test" "$tmp/c14/err.log"; then
        echo "PASS: c14 rejected Widget redefinition"
    else
        echo "FAIL: c14 did not report expected Widget redefinition error" >&2
        fail=1
    fi
fi

# Case 15: test does not import target implementation module -> rejected
mkdir -p "$tmp/c15/lib" "$tmp/c15/tests"
cat > "$tmp/c15/lib/widget_impl.py" <<'EOF'
class Widget:
    pass
EOF
cat > "$tmp/c15/tests/widget_impl_test.py" <<'EOF'
import unittest
class WidgetTest(unittest.TestCase):
    def test_basic(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c15" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/widget_impl_test.py --lib-pkg lib 2>"$tmp/c15/err.log" ); then
    echo "FAIL: c15 expected failure when test does not import target implementation" >&2
    fail=1
else
    if grep -q "test module must import target implementation module 'lib.widget_impl'" "$tmp/c15/err.log"; then
        echo "PASS: c15 rejected test missing target implementation import"
    else
        echo "FAIL: c15 did not report missing target import error" >&2
        fail=1
    fi
fi

# Case 16: test file with bare target import and cross-part import -> rewritten and added to pyright_deps.
mkdir -p "$tmp/c16/lib" "$tmp/c16/tests"
cat > "$tmp/c16/lib/widget_impl.py" <<'EOF'
class Widget:
    pass
EOF
cat > "$tmp/c16/tests/widget_impl_test.py" <<'EOF'
import unittest
from widget_impl import Widget
from dag_storage import DagStorage

class WidgetTest(unittest.TestCase):
    def test_basic(self):
        w = Widget()
        self.assertIsNotNone(w)

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c16" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/widget_impl_test.py --lib-pkg lib --deps //update_with_ai/parts/dag/lib:dag_storage ); then
    echo "PASS: c16 accepted and rewrote bare target and cross-part imports"
else
    echo "FAIL: c16 expected success with import rewriting" >&2
    fail=1
fi
check "c16 rewritten target import" "$tmp/c16/tests/widget_impl_test.py" 'from lib\.widget_impl import Widget'
check "c16 rewritten cross-part import" "$tmp/c16/tests/widget_impl_test.py" 'from update_with_ai\.parts\.dag\.lib\.dag_storage import DagStorage'
check "c16 cross-part dep in BUILD" "$tmp/c16/tests/BUILD.bazel" '"//update_with_ai/parts/dag/lib:dag_storage"'

# Case 17: lifecycle import in test -> rewritten to support.lib.lifecycle.
mkdir -p "$tmp/c17/lib" "$tmp/c17/tests"
cat > "$tmp/c17/lib/widget_impl.py" <<'EOF'
class Widget:
    pass
EOF
cat > "$tmp/c17/tests/widget_impl_test.py" <<'EOF'
import unittest
from lib.widget_impl import Widget
from lifecycle import LifecycleRegistry

class WidgetTest(unittest.TestCase):
    def test_lifecycle(self):
        reg = LifecycleRegistry()
        self.assertIsNotNone(reg)

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c17" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/widget_impl_test.py --lib-pkg lib ); then
    echo "PASS: c17 accepted and rewrote lifecycle import in test"
else
    echo "FAIL: c17 expected success with test lifecycle rewriting" >&2
    fail=1
fi
check "c17 rewritten lifecycle" "$tmp/c17/tests/widget_impl_test.py" 'from support\.lib\.lifecycle import LifecycleRegistry'
check "c17 lifecycle in BUILD" "$tmp/c17/tests/BUILD.bazel" '"//update_python_with_ai/support/lib:lifecycle"'

# Case 18: dependency header maintained at top of test file.
mkdir -p "$tmp/c18/lib" "$tmp/c18/tests"
cat > "$tmp/c18/lib/widget_impl.py" <<'EOF'
class Widget:
    pass
EOF
cat > "$tmp/c18/tests/widget_impl_test.py" <<'EOF'
import unittest
from lib.widget_impl import Widget

class WidgetTest(unittest.TestCase):
    def test_widget(self):
        pass

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c18" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/widget_impl_test.py --lib-pkg lib --deps //update_with_ai/parts/dag/lib:dag_storage ); then
    echo "PASS: c18 passed test_lint"
else
    echo "FAIL: c18 expected success in test_lint" >&2
    fail=1
fi
if grep -q '# Dependencies:' "$tmp/c18/tests/widget_impl_test.py"; then
    echo "FAIL: c18 unexpected dependency comment line" >&2
    fail=1
else
    echo "PASS: c18 no dependency comment line present"
fi

# Case 19: undeclared dependency import in test fails with diagnostic listing allowed dependencies.
mkdir -p "$tmp/c19/lib" "$tmp/c19/tests"
cat > "$tmp/c19/lib/widget_impl.py" <<'EOF'
class Widget:
    pass
EOF
cat > "$tmp/c19/tests/widget_impl_test.py" <<'EOF'
import unittest
from lib.widget_impl import Widget
import unauthorized_module

class WidgetTest(unittest.TestCase):
    def test_widget(self):
        pass

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c19" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/widget_impl_test.py --lib-pkg lib 2>"$tmp/c19/err.log" ); then
    echo "FAIL: c19 expected failure on undeclared import in test" >&2
    fail=1
else
    echo "PASS: c19 rejected undeclared import in test"
fi
check "c19 undeclared error diagnostic" "$tmp/c19/err.log" "undeclared dependency 'unauthorized_module'. Allowed dependencies: widget_impl"

# Case 20: empty test module with .pyi grounding spec -> scaffolded with valid test skeleton.
mkdir -p "$tmp/c20/lib" "$tmp/c20/tests" "$tmp/c20/grounding"
cat > "$tmp/c20/grounding/worker_impl.pyi" <<'EOF'
from support.lib.framework import operation, singleton_type

@singleton_type('agent_session')
class Worker:
    """
PURPOSE:
Worker component.

FRESH_REQUIREMENTS:
- The worker processes items sequentially.
- Processing an item returns true on success.
"""
    @operation
    def process_item(self, item: str) -> bool:
        ...
EOF
cat > "$tmp/c20/lib/worker_impl.py" <<'EOF'
class Worker:
    pass

def __initialize__(registry=None):
    pass
EOF
touch "$tmp/c20/tests/worker_impl_test.py"
if ( cd "$tmp/c20" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/worker_impl_test.py --lib-pkg lib --pyi "$tmp/c20/grounding/worker_impl.pyi" 2>"$tmp/c20/uninit.log" ); then
    echo "FAIL: c20 expected rejection of empty test module without --scaffold" >&2
    fail=1
else
    echo "PASS: c20 rejected empty test module without --scaffold"
fi
check "c20 uninit diagnostic" "$tmp/c20/uninit.log" "tests/worker_impl_test.py is uninitialized"

if ( cd "$tmp/c20" && python3 "$bin/test_lint.py" --scaffold tests/worker_impl_test.py --lib-pkg lib --pyi "$tmp/c20/grounding/worker_impl.pyi" ); then
    echo "PASS: c20 generated test skeleton via --scaffold"
else
    echo "FAIL: c20 failed to generate test skeleton via --scaffold" >&2
    fail=1
fi

if ( cd "$tmp/c20" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/worker_impl_test.py --lib-pkg lib --pyi "$tmp/c20/grounding/worker_impl.pyi" ); then
    echo "PASS: c20 validated generated test skeleton"
else
    echo "FAIL: c20 failed to validate generated test skeleton" >&2
    fail=1
fi
check "c20 target class import" "$tmp/c20/tests/worker_impl_test.py" 'from lib\.worker_impl import'
check "c20 worker imported" "$tmp/c20/tests/worker_impl_test.py" 'Worker,'
check "c20 initialize imported" "$tmp/c20/tests/worker_impl_test.py" '__initialize__,'
check "c20 test class" "$tmp/c20/tests/worker_impl_test.py" 'class WorkerImplTest(unittest\.TestCase):'
check "c20 setup method" "$tmp/c20/tests/worker_impl_test.py" 'def setUp(self) -> None:'
check "c20 cuj method" "$tmp/c20/tests/worker_impl_test.py" 'def test_initialization(self) -> None:'
check "c20 unittest main" "$tmp/c20/tests/worker_impl_test.py" 'if __name__ == "__main__":'
check "c20 untested req header" "$tmp/c20/tests/worker_impl_test.py" '# Untested requirements:'
check "c20 untested req item" "$tmp/c20/tests/worker_impl_test.py" '# - The worker processes items sequentially\.'
check "c20 untested req item 2" "$tmp/c20/tests/worker_impl_test.py" '# - Processing an item returns true on success\.'

# Case 21: test module with <TargetClass> placeholder -> replaced with auto-generated test skeleton.
mkdir -p "$tmp/c21/lib" "$tmp/c21/tests" "$tmp/c21/grounding"
cat > "$tmp/c21/grounding/service_impl.pyi" <<'EOF'
from support.lib.framework import operation, singleton_type

@singleton_type('system')
class Service:
    """
PURPOSE:
Service component.

INHERITED_REQUIREMENTS:
- [Service] The service initializes system state.
"""
    @operation
    def serve(self) -> None:
        ...
EOF
cat > "$tmp/c21/lib/service_impl.py" <<'EOF'
class Service:
    pass

def __initialize__(registry=None):
    pass
EOF
cat > "$tmp/c21/tests/service_impl_test.py" <<'EOF'
class <TargetClass>Test(unittest.TestCase):
    pass
EOF
if ( cd "$tmp/c21" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/service_impl_test.py --lib-pkg lib --pyi "$tmp/c21/grounding/service_impl.pyi" 2>"$tmp/c21/uninit.log" ); then
    echo "FAIL: c21 expected rejection of <TargetClass> placeholder without --scaffold" >&2
    fail=1
else
    echo "PASS: c21 rejected <TargetClass> placeholder without --scaffold"
fi
check "c21 uninit diagnostic" "$tmp/c21/uninit.log" "tests/service_impl_test.py is uninitialized"

if ( cd "$tmp/c21" && python3 "$bin/test_lint.py" --scaffold tests/service_impl_test.py --lib-pkg lib --pyi "$tmp/c21/grounding/service_impl.pyi" ); then
    echo "PASS: c21 replaced <TargetClass> test placeholder via --scaffold"
else
    echo "FAIL: c21 failed to replace <TargetClass> test placeholder via --scaffold" >&2
    fail=1
fi

if ( cd "$tmp/c21" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/service_impl_test.py --lib-pkg lib --pyi "$tmp/c21/grounding/service_impl.pyi" ); then
    echo "PASS: c21 validated replaced test skeleton"
else
    echo "FAIL: c21 failed to validate replaced test skeleton" >&2
    fail=1
fi
check "c21 service class import" "$tmp/c21/tests/service_impl_test.py" 'from lib\.service_impl import'
check "c21 service imported" "$tmp/c21/tests/service_impl_test.py" 'Service,'
check "c21 service test class" "$tmp/c21/tests/service_impl_test.py" 'class ServiceImplTest(unittest\.TestCase):'
check "c21 untested requirement" "$tmp/c21/tests/service_impl_test.py" '# - \[Service\] The service initializes system state\.'

# Case 22: parent package BUILD.bazel contains _ext dependency -> excluded from tests/BUILD.bazel
mkdir -p "$tmp/c22/lib" "$tmp/c22/tests" "$tmp/c22/grounding"
cat > "$tmp/c22/BUILD.bazel" <<'EOF'
load("@rules_python//python:defs.bzl", "py_library")

py_library(
    name = "worker_impl",
    srcs = ["lib/worker_impl.py"],
    deps = [
        "//other/pkg:helper_ext",
        ":helper_ext",
        "//other/pkg:common",
    ],
)
EOF
cat > "$tmp/c22/grounding/worker_impl.pyi" <<'EOF'
class Worker:
    pass
EOF
cat > "$tmp/c22/lib/worker_impl.py" <<'EOF'
class Worker:
    pass
def __initialize__(registry=None):
    pass
EOF
cat > "$tmp/c22/tests/worker_impl_test.py" <<'EOF'
import unittest
from lib.worker_impl import Worker

class WorkerTest(unittest.TestCase):
    def test_ok(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c22" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/worker_impl_test.py --lib-pkg lib --pyi "$tmp/c22/grounding/worker_impl.pyi" ); then
    echo "PASS: c22 ran test_lint with _ext in parent deps"
else
    echo "FAIL: c22 failed to run test_lint with _ext in parent deps" >&2
    fail=1
fi
if grep -q "helper_ext" "$tmp/c22/tests/BUILD.bazel"; then
    echo "FAIL: c22 included _ext dependency in tests/BUILD.bazel" >&2
    fail=1
else
    echo "PASS: c22 correctly excluded _ext dependency from tests/BUILD.bazel"
fi

# Case 24: test module importing foreign _impl -> fails with impl error
mkdir -p "$tmp/c24/lib" "$tmp/c24/tests" "$tmp/c24/grounding"
cat > "$tmp/c24/grounding/unit_impl.pyi" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c24/tests/unit_impl_test.py" <<'EOF'
import unittest
from lib.unit_impl import Foo
from lib.other_impl import OtherFoo

class UnitTest(unittest.TestCase):
    def test_ok(self):
        pass
if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c24" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/unit_impl_test.py --lib-pkg lib --pyi "$tmp/c24/grounding/unit_impl.pyi" 2>"$tmp/c24/err.log" ); then
    echo "FAIL: c24 expected failure on foreign _impl import" >&2
    fail=1
else
    echo "PASS: c24 rejected foreign _impl import in test"
fi
check "c24 foreign impl error diagnostic" "$tmp/c24/err.log" "test module must only import target implementation module 'unit_impl', but imports from 'lib.other_impl'"

# Case 25: pure-Python test_lint invocation on test file with --pyi -> succeeds without creating BUILD.bazel
mkdir -p "$tmp/c25/lib" "$tmp/c25/tests" "$tmp/c25/low"
cat > "$tmp/c25/low/worker_impl.pyi" <<'EOF'
from support.lib.framework import operation, singleton_type

@singleton_type('agent_session')
class Worker:
    @operation
    def process_item(self, item: str) -> bool:
        ...
EOF
cat > "$tmp/c25/lib/worker_impl.py" <<'EOF'
class Worker:
    def process_item(self, item: str) -> bool:
        return True
EOF
cat > "$tmp/c25/tests/worker_impl_test.py" <<'EOF'
import unittest
from lib.worker_impl import Worker

class WorkerTest(unittest.TestCase):
    def test_process(self):
        w = Worker()
        self.assertTrue(w.process_item("test"))

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c25" && python3 "$bin/test_lint.py" tests/worker_impl_test.py --pyi low/worker_impl.pyi ); then
    echo "PASS: c25 pure-Python test_lint succeeded"
else
    echo "FAIL: c25 expected pass on pure-Python test_lint" >&2
    fail=1
fi
if [ -f "$tmp/c25/tests/BUILD.bazel" ] || [ -f "$tmp/c25/BUILD.bazel" ]; then
    echo "FAIL: c25 BUILD.bazel should not be created" >&2
    fail=1
else
    echo "PASS: c25 no BUILD.bazel created"
fi

# Case 26: pure-Python test_lint invocation with undeclared import -> fails and creates no BUILD.bazel
mkdir -p "$tmp/c26/lib" "$tmp/c26/tests" "$tmp/c26/low"
cat > "$tmp/c26/low/worker_impl.pyi" <<'EOF'
from support.lib.framework import operation, singleton_type

@singleton_type('agent_session')
class Worker:
    @operation
    def process_item(self, item: str) -> bool:
        ...
EOF
cat > "$tmp/c26/lib/worker_impl.py" <<'EOF'
class Worker:
    def process_item(self, item: str) -> bool:
        return True
EOF
cat > "$tmp/c26/tests/worker_impl_test.py" <<'EOF'
import unittest
import unauthorized_package
from lib.worker_impl import Worker

class WorkerTest(unittest.TestCase):
    def test_process(self):
        w = Worker()
        self.assertTrue(w.process_item("test"))

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c26" && python3 "$bin/test_lint.py" tests/worker_impl_test.py --pyi low/worker_impl.pyi 2>"$tmp/c26/err.log" ); then
    echo "FAIL: c26 expected failure on undeclared import" >&2
    fail=1
else
    if grep -q "undeclared dependency 'unauthorized_package'" "$tmp/c26/err.log"; then
        echo "PASS: c26 rejected undeclared import in pure-Python mode"
    else
        echo "FAIL: c26 did not report undeclared dependency in err.log" >&2
        cat "$tmp/c26/err.log" >&2
        fail=1
    fi
fi
if [ -f "$tmp/c26/tests/BUILD.bazel" ] || [ -f "$tmp/c26/BUILD.bazel" ]; then
    echo "FAIL: c26 BUILD.bazel should not be created" >&2
else
    echo "PASS: c26 no BUILD.bazel created on failure"
fi

# Case 27: companion lib module is missing -> automatically scaffolded during test scaffold and verification
mkdir -p "$tmp/c27/tests" "$tmp/c27/low"
cat > "$tmp/c27/low/worker_impl.pyi" <<'EOF'
from support.lib.lifecycle import operation, singleton_type

@singleton_type('system')
class Worker:
    """
PURPOSE:
Worker component.

FRESH_REQUIREMENTS:
- The worker processes items sequentially.
- Processing an item returns true on success.
"""
    @operation
    def process_item(self, item: str) -> bool:
        ...
EOF
touch "$tmp/c27/tests/worker_impl_test.py"
if ( cd "$tmp/c27" && python3 "$bin/test_lint.py" --scaffold tests/worker_impl_test.py --pyi low/worker_impl.pyi ); then
    echo "PASS: c27 generated test skeleton via --scaffold with missing lib"
else
    echo "FAIL: c27 failed to generate test skeleton via --scaffold with missing lib" >&2
    fail=1
fi
if [ -f "$tmp/c27/lib/worker_impl.py" ]; then
    echo "PASS: c27 companion lib module was automatically scaffolded"
else
    echo "FAIL: c27 companion lib module was not scaffolded" >&2
    fail=1
fi
if ( cd "$tmp/c27" && python3 "$bin/test_lint.py" tests/worker_impl_test.py --pyi low/worker_impl.pyi ); then
    echo "PASS: c27 dry-run test collection succeeded against scaffolded companion lib"
else
    echo "FAIL: c27 dry-run test collection failed against scaffolded companion lib" >&2
    fail=1
fi

# Case 28: test module using getattr() -> rejected with contract adherence error
mkdir -p "$tmp/c28/lib" "$tmp/c28/tests"
cat > "$tmp/c28/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c28/tests/foo_test.py" <<'EOF'
import unittest
from lib.foo import Foo

class FooTest(unittest.TestCase):
    def test_foo(self):
        f = Foo()
        val = getattr(f, "bar", None)

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c28" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>"$tmp/c28/err.log" ); then
    echo "FAIL: c28 expected failure when getattr() used in test" >&2
    fail=1
else
    if grep -q "test module must not use 'getattr()'" "$tmp/c28/err.log"; then
        echo "PASS: c28 rejected test using getattr() and reported contract error"
    else
        echo "FAIL: c28 did not report getattr error in err.log" >&2
        cat "$tmp/c28/err.log" >&2
        fail=1
    fi
fi

# Case 29: scoped package test file rejects unrooted lib imports and scaffolding generates scoped imports
mkdir -p "$tmp/c29/pkg/parts/unit/lib" "$tmp/c29/pkg/parts/unit/tests" "$tmp/c29/pkg/parts/unit/low"
cat > "$tmp/c29/cleanroom.toml" <<'EOF'
EOF
cat > "$tmp/c29/pkg/parts/unit/low/worker_impl.pyi" <<'EOF'
from support.lib.framework import operation, singleton_type

@singleton_type('agent_session')
class Worker:
    """
PURPOSE:
Worker component.

INHERITED_REQUIREMENTS:
- [Worker] Processes item.
"""
    @operation
    def process_item(self, item: str) -> bool:
        ...
EOF
cat > "$tmp/c29/pkg/parts/unit/lib/worker_impl.py" <<'EOF'
class Worker:
    def process_item(self, item: str) -> bool:
        return True
def __initialize__(registry=None):
    pass
EOF
# Test scaffolding generates scoped import
if ( cd "$tmp/c29" && python3 "$bin/test_lint.py" --scaffold pkg/parts/unit/tests/worker_impl_test.py --lib-pkg pkg/parts/unit/lib --pyi pkg/parts/unit/low/worker_impl.pyi ); then
    echo "PASS: c29 generated scaffold for scoped package"
else
    echo "FAIL: c29 failed to generate scaffold for scoped package" >&2
    fail=1
fi
check "c29 scaffold has scoped import" "$tmp/c29/pkg/parts/unit/tests/worker_impl_test.py" 'from pkg\.parts\.unit\.lib\.worker_impl import'

# Write unrooted import (from lib import worker_impl) -> must fail test_lint
cat > "$tmp/c29/pkg/parts/unit/tests/worker_impl_test.py" <<'EOF'
import unittest
from lib import worker_impl

class WorkerImplTest(unittest.TestCase):
    def test_process(self):
        pass

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c29" && python3 "$bin/test_lint.py" pkg/parts/unit/tests/worker_impl_test.py --lib-pkg pkg/parts/unit/lib --pyi pkg/parts/unit/low/worker_impl.pyi 2>"$tmp/c29/err.log" ); then
    echo "FAIL: c29 expected rejection of from lib import in scoped package" >&2
    fail=1
else
    if grep -q "error: import of lib module" "$tmp/c29/err.log"; then
        echo "PASS: c29 rejected from lib import in scoped package"
    else
        echo "FAIL: c29 did not report import error for from lib import" >&2
        cat "$tmp/c29/err.log" >&2
        fail=1
    fi
fi

# Write unrooted import (from lib.worker_impl import Worker) -> must fail test_lint
cat > "$tmp/c29/pkg/parts/unit/tests/worker_impl_test.py" <<'EOF'
import unittest
from lib.worker_impl import Worker

class WorkerImplTest(unittest.TestCase):
    def test_process(self):
        pass

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c29" && python3 "$bin/test_lint.py" pkg/parts/unit/tests/worker_impl_test.py --lib-pkg pkg/parts/unit/lib --pyi pkg/parts/unit/low/worker_impl.pyi 2>"$tmp/c29/err2.log" ); then
    echo "FAIL: c29 expected rejection of from lib.worker_impl import in scoped package" >&2
    fail=1
else
    if grep -q "error: import of lib module" "$tmp/c29/err2.log"; then
        echo "PASS: c29 rejected from lib.worker_impl import in scoped package"
    else
        echo "FAIL: c29 did not report import error for from lib.worker_impl import" >&2
        cat "$tmp/c29/err2.log" >&2
        fail=1
    fi
fi

# Case 30: test module using cast(Any, ...).attr -> rejected with contract adherence error
mkdir -p "$tmp/c30/lib" "$tmp/c30/tests"
cat > "$tmp/c30/lib/foo.py" <<'EOF'
class Foo:
    def execute(self) -> None:
        pass
EOF
cat > "$tmp/c30/tests/foo_test.py" <<'EOF'
import unittest
from typing import Any, cast
from lib.foo import Foo

class FooTest(unittest.TestCase):
    def test_foo(self):
        f = Foo()
        cast(Any, f).configure()

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c30" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>"$tmp/c30/err.log" ); then
    echo "FAIL: c30 expected failure when cast(Any, ...).attr used in test" >&2
    fail=1
else
    if grep -q "test module must not access attribute or method 'configure' on 'cast(Any, ...)'" "$tmp/c30/err.log"; then
        echo "PASS: c30 rejected test accessing method on cast(Any, ...) and reported contract error"
    else
        echo "FAIL: c30 did not report cast(Any, ...) attribute error in err.log" >&2
        cat "$tmp/c30/err.log" >&2
        fail=1
    fi
fi

# Case 31: test module accessing private member on target object -> rejected with contract adherence error
mkdir -p "$tmp/c31/lib" "$tmp/c31/tests"
cat > "$tmp/c31/lib/foo.py" <<'EOF'
class Foo:
    def __init__(self):
        self._secret = 42
EOF
cat > "$tmp/c31/tests/foo_test.py" <<'EOF'
import unittest
from lib.foo import Foo

class FooTest(unittest.TestCase):
    def test_foo(self):
        f = Foo()
        val = f._secret

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c31" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>"$tmp/c31/err.log" ); then
    echo "FAIL: c31 expected failure when private member accessed on target object in test" >&2
    fail=1
else
    if grep -q "test module must not access private member '_secret' on target or collaborator object" "$tmp/c31/err.log"; then
        echo "PASS: c31 rejected test accessing private member on target and reported contract error"
    else
        echo "FAIL: c31 did not report private member error in err.log" >&2
        cat "$tmp/c31/err.log" >&2
        fail=1
    fi
fi

# Case 32: test module using setattr() -> rejected with contract adherence error
mkdir -p "$tmp/c32/lib" "$tmp/c32/tests"
cat > "$tmp/c32/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c32/tests/foo_test.py" <<'EOF'
import unittest
from lib.foo import Foo

class FooTest(unittest.TestCase):
    def test_foo(self):
        f = Foo()
        setattr(f, "bar", 123)

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c32" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>"$tmp/c32/err.log" ); then
    echo "FAIL: c32 expected failure when setattr() used in test" >&2
    fail=1
else
    if grep -q "test module must not use 'setattr()'" "$tmp/c32/err.log"; then
        echo "PASS: c32 rejected test using setattr() and reported contract error"
    else
        echo "FAIL: c32 did not report setattr error in err.log" >&2
        cat "$tmp/c32/err.log" >&2
        fail=1
    fi
fi

# Case 33: scaffold non-impl module with classes and functions and verify lib import diagnostics
mkdir -p "$tmp/c33/pkg/parts/unit/lib" "$tmp/c33/pkg/parts/unit/tests" "$tmp/c33/pkg/parts/unit/low"
cat > "$tmp/c33/cleanroom.toml" <<'EOF'
EOF
cat > "$tmp/c33/pkg/parts/unit/low/engine.pyi" <<'EOF'
from support.lib.framework import operation

class Engine:
    @operation
    def run(self) -> None:
        ...

def create_engine() -> Engine:
    ...
EOF
cat > "$tmp/c33/pkg/parts/unit/lib/engine.py" <<'EOF'
class Engine:
    def run(self) -> None:
        pass
def create_engine() -> Engine:
    return Engine()
EOF
if ( cd "$tmp/c33" && python3 "$bin/test_lint.py" --scaffold pkg/parts/unit/tests/engine_test.py --lib-pkg pkg/parts/unit/lib --pyi pkg/parts/unit/low/engine.pyi ); then
    echo "PASS: c33 scaffolded non-impl module"
else
    echo "FAIL: c33 failed to scaffold non-impl module" >&2
    fail=1
fi
check "c33 scaffold imported Engine" "$tmp/c33/pkg/parts/unit/tests/engine_test.py" 'Engine,'
check "c33 scaffold imported create_engine" "$tmp/c33/pkg/parts/unit/tests/engine_test.py" 'create_engine,'

# Write bare import of engine -> check_test_imports directs to pkg-qualified, not undeclared
cat > "$tmp/c33/pkg/parts/unit/tests/engine_test.py" <<'EOF'
import unittest
from engine import Engine

class EngineTest(unittest.TestCase):
    def test_run(self):
        pass

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c33" && python3 "$bin/test_lint.py" pkg/parts/unit/tests/engine_test.py --lib-pkg pkg/parts/unit/lib --pyi pkg/parts/unit/low/engine.pyi 2>"$tmp/c33/err.log" ); then
    echo "FAIL: c33 expected failure on bare import of engine" >&2
    fail=1
else
    if grep -q "error: import of lib module 'engine' must be 'from pkg.parts.unit.lib.engine import ...'" "$tmp/c33/err.log"; then
        echo "PASS: c33 import error directs to package-qualified path"
    else
        echo "FAIL: c33 did not direct to package-qualified path in err.log" >&2
        cat "$tmp/c33/err.log" >&2
        fail=1
    fi
    if grep -q "undeclared dependency 'engine'" "$tmp/c33/err.log"; then
        echo "FAIL: c33 should not report local lib module as undeclared dependency" >&2
        fail=1
    else
        echo "PASS: c33 did not falsely report local lib module as undeclared dependency"
    fi
fi

# Case 34: test module using hasattr() -> rejected with contract adherence error
mkdir -p "$tmp/c34/lib" "$tmp/c34/tests"
cat > "$tmp/c34/lib/foo.py" <<'EOF'
class Foo:
    pass
EOF
cat > "$tmp/c34/tests/foo_test.py" <<'EOF'
import unittest
from lib.foo import Foo

class FooTest(unittest.TestCase):
    def test_foo(self):
        f = Foo()
        val = hasattr(f, "bar")

if __name__ == "__main__":
    unittest.main()
EOF
if ( cd "$tmp/c34" && python3 "$bin/test_lint.py" tests/BUILD.bazel tests/foo_test.py --lib-pkg lib 2>"$tmp/c34/err.log" ); then
    echo "FAIL: c34 expected failure when hasattr() used in test" >&2
    fail=1
else
    if grep -q "test module must not use 'hasattr()'" "$tmp/c34/err.log"; then
        echo "PASS: c34 rejected test using hasattr() and reported contract error"
    else
        echo "FAIL: c34 did not report hasattr error in err.log" >&2
        cat "$tmp/c34/err.log" >&2
        fail=1
    fi
fi

exit "$fail"



