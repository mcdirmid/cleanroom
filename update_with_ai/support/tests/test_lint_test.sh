#!/bin/bash
# test_lint_test.sh — gate: test_lint.py creates/fixes pyright_test entries.

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
from testing.lib.foo import Foo
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

exit "$fail"

