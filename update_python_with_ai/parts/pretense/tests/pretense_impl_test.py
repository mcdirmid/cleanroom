"""Unit tests for pretense_impl conforming strictly to public contracts."""

import unittest
from dataclasses import dataclass, field
from typing import Any, List, Optional
from pathlib import Path

import hypothesis.strategies as st
from hypothesis.stateful import run_state_machine_as_test
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from update_python_with_ai.parts.pretense.lib import pretense
from update_python_with_ai.parts.pretense.lib import pretense_impl
from update_python_with_ai.parts.pretense.lib.pretense_impl import (
    ActiveStepTracker,
    PretenseEngine,
    WatchdogMonitor,
    compile_hypothesis_test_case,
    main,
    run_pretense_cli,
)


class DummyCounter:
    def __init__(self) -> None:
        self.count: int = 0

    def increment(self, step: int = 1) -> int:
        self.count += step
        return self.count

    def reset(self) -> None:
        self.count = 0


class PretenseImplTest(unittest.TestCase):
    def setUp(self) -> None:
        pretense_impl.__initialize__()

    def test_sentinels_and_outcomes(self) -> None:
        """Verify sentinel behavior, equality, and unwrapping."""
        nb = pretense.NotBound
        self.assertFalse(bool(nb))
        self.assertEqual(repr(nb), "NotBound")

        val = pretense.Value(42)
        self.assertEqual(val.unwrap(), 42)
        self.assertEqual(val, pretense.Value(42))
        self.assertNotEqual(val, pretense.Value(43))

        exc = ValueError("boom")
        raised = pretense.Raised(exc)
        self.assertEqual(raised.message, "boom")
        with self.assertRaises(ValueError):
            raised.unwrap()

    def test_transition_and_state_machine(self) -> None:
        """Verify transition registration, execution, and invariant checking."""
        t_inc = pretense.Transition("increment")
        t_inc.require(lambda state, this: state["count"] >= 0)
        t_inc.arguments(lambda state, this, *args: (1,) if not args else args)
        t_inc.returns(lambda state, this, *args, outcome=pretense.NotBound: pretense.Value(state["count"] + args[0]))
        t_inc.provide(lambda state, this, *args, result=None: state.__setitem__("count", state["count"] + args[0]))

        state = {"count": 0}
        inv_called = [False]

        def check_positive(st: Any, sm: Any) -> None:
            self.assertGreaterEqual(st["count"], 0)
            inv_called[0] = True

        sm = pretense.StateMachine(
            state=state,
            transitions=[t_inc],
            invariants=[check_positive],
        )

        res = sm.dispatch_transition("increment", 5)
        self.assertEqual(res, 5)
        self.assertEqual(state["count"], 5)
        self.assertTrue(inv_called[0])

    def test_fake_adapter_dispatch(self) -> None:
        """Verify fake adapter dispatches method calls to matching transitions."""
        t_inc = pretense.Transition("increment")
        t_inc.arguments(lambda state, this, *args, **kwargs: (args[0] if args else 1,))
        t_inc.returns(lambda state, this, *args, outcome=pretense.NotBound: pretense.Value(state["count"] + args[0]))
        t_inc.provide(lambda state, this, *args, result=None: state.__setitem__("count", state["count"] + args[0]))

        class CounterProto:
            def increment(self, step: int = 1) -> int: ...

        state = {"count": 10}
        sm = pretense.StateMachine(state=state, transitions=[t_inc])
        fake = sm.as_fake(CounterProto)

        result = fake.increment(2)
        self.assertEqual(result, 12)
        self.assertEqual(state["count"], 12)

    def test_class_based_state_machine_with_transition_context(self) -> None:
        """Verify class-based StateMachine with @transition methods and TransitionContext."""
        from dataclasses import dataclass, field
        from hypothesis.stateful import run_state_machine_as_test

        @dataclass
        class CounterState:
            count: int = 0
            history: list[int] = field(default_factory=list)

        class RealCounter:
            def __init__(self) -> None:
                self.val: int = 0

            def increment(self, step: int = 1) -> int:
                self.val += step
                return self.val

            def reset(self) -> None:
                self.val = 0

        class CounterStateMachine(pretense.StateMachine[CounterState]):
            def __init__(
                self,
                state: Optional[CounterState] = None,
                singletons: Optional[dict[type[Any], Any]] = None,
            ) -> None:
                super().__init__(state=state or CounterState(), singletons=singletons)

            @pretense.transition(RealCounter.increment)
            def step_inc(self, ctx: pretense.TransitionContext[RealCounter, [int], int]) -> None:
                ctx.antecedent(lambda: self.state.count < 100)
                ctx.arguments(
                    step=pretense.Domain(strategy=lambda: 1, validator=lambda step=1: step > 0),
                )
                ctx.returns(lambda step=1: self.state.count + step)
                ctx.consequent(lambda res, step=1: (
                    setattr(self.state, "count", self.state.count + step),
                    self.state.history.append(step),
                ))

            @pretense.transition(RealCounter.reset)
            def step_reset(self, ctx: pretense.TransitionContext[RealCounter, [], None]) -> None:
                ctx.antecedent(lambda: self.state.count > 0)
                ctx.arguments()
                ctx.returns(lambda: None)
                ctx.consequent(lambda: setattr(self.state, "count", 0))

            def invariant_non_negative(self) -> None:
                assert self.state.count >= 0, "count must not be negative"

        # 1. Verify Fake Adapter behavior
        sm = CounterStateMachine()
        fake = sm.as_fake(RealCounter)
        res = fake.increment(5)
        self.assertEqual(res, 5)
        self.assertEqual(sm.state.count, 5)
        self.assertEqual(sm.state.history, [5])

        fake.reset()
        self.assertEqual(sm.state.count, 0)

        # 2. Verify Hypothesis test case generation and execution
        real = RealCounter()
        test_sm = CounterStateMachine(singletons={RealCounter: real})
        test_case_cls = test_sm.to_hypothesis_test_case()
        run_state_machine_as_test(test_case_cls)

    def test_transition_context_raises(self) -> None:
        """Verify error specification with ctx.raises."""
        class Divider:
            def divide(self, a: int, b: int) -> int:
                if b == 0:
                    raise ZeroDivisionError("division by zero")
                return a // b

        class DividerStateMachine(pretense.StateMachine[dict[str, Any]]):
            def __init__(self, singletons: Optional[dict[type[Any], Any]] = None) -> None:
                super().__init__(state={}, singletons=singletons)

            @pretense.transition(Divider.divide)
            def divide_by_zero(self, ctx: pretense.TransitionContext[Divider, [int, int], int]) -> None:
                ctx.arguments(
                    a=pretense.Domain(strategy=lambda: 10, validator=lambda a: True),
                    b=pretense.Domain(strategy=lambda: 0, validator=lambda b: b == 0),
                )
                ctx.raises(ZeroDivisionError, match="division by zero")

        # Fake raises ZeroDivisionError
        sm = DividerStateMachine()
        fake = sm.as_fake(Divider)
        with self.assertRaises(ZeroDivisionError):
            fake.divide(10, 0)

    def test_active_step_tracker(self) -> None:
        """Verify active step tracking and diagnostic formatting."""
        # When no step is active, diagnostic is empty string
        diag = ActiveStepTracker.format_active_step_diagnostic()
        self.assertEqual(diag, "")
        self.assertIsNone(ActiveStepTracker.get_active_step())

    def test_watchdog_arm_and_disarm(self) -> None:
        """Verify watchdog monitor handles arming and clean disarming."""
        # Arming with 0 or negative timeout is a no-op
        handle_zero = WatchdogMonitor.arm(0.0)
        self.assertIsNone(handle_zero)
        WatchdogMonitor.disarm(handle_zero)

        # Arming with positive timeout returns a handle that can be disarmed
        handle = WatchdogMonitor.arm(10.0, target_name="test_target")
        self.assertIsNotNone(handle)
        WatchdogMonitor.disarm(handle)

    def test_transition_context_mutual_exclusivity(self) -> None:
        """Verify that declaring both ctx.raises and ctx.returns raises ValueError."""
        ctx1 = pretense.TransitionContext(name="step_a")
        ctx1.returns(lambda: 42)
        with self.assertRaises(ValueError) as cm:
            ctx1.raises(ValueError)
        self.assertIn("cannot declare both ctx.raises(...) and ctx.returns(...)", str(cm.exception))

        ctx2 = pretense.TransitionContext(name="step_b")
        ctx2.raises(ValueError)
        with self.assertRaises(ValueError) as cm:
            ctx2.returns(lambda: 42)
        self.assertIn("cannot declare both ctx.raises(...) and ctx.returns(...)", str(cm.exception))

    def test_safe_instantiate_multi_argument_exception(self) -> None:
        """Verify that fake adapter safely instantiates multi-argument dataclass exceptions."""
        from dataclasses import dataclass

        @dataclass
        class MultiArgError(Exception):
            message: str
            package_name: str
            code: int = 404

        class PkgRepo:
            def find_pkg(self, name: str) -> str:
                return name

        class PkgRepoStateMachine(pretense.StateMachine[dict[str, Any]]):
            def __init__(self, singletons: Optional[dict[type[Any], Any]] = None) -> None:
                super().__init__(state={}, singletons=singletons)

            @pretense.transition(PkgRepo.find_pkg)
            def missing_pkg(self, ctx: pretense.TransitionContext[PkgRepo, [str], str]) -> None:
                ctx.arguments(name=pretense.Domain(strategy=lambda: "ghost", validator=lambda name: name == "ghost"))
                ctx.raises(MultiArgError, match="ghost not found")

        sm = PkgRepoStateMachine()
        fake = sm.as_fake(PkgRepo)
        with self.assertRaises(MultiArgError) as cm:
            fake.find_pkg("ghost")
        self.assertIn("ghost not found", str(cm.exception))
        self.assertEqual(cm.exception.package_name, "<mock_package_name>")

    def test_return_contract_violation_diagnostic_reason(self) -> None:
        """Verify that diagnostic reason is included when SUT produces value on ctx.raises transition."""
        class EchoService:
            def echo(self, text: str) -> str:
                return text

        class EchoStateMachine(pretense.StateMachine[dict[str, Any]]):
            def __init__(self, singletons: Optional[dict[type[Any], Any]] = None) -> None:
                super().__init__(state={}, singletons=singletons)

            @pretense.transition(EchoService.echo)
            def echo_step(self, ctx: pretense.TransitionContext[EchoService, [str], str]) -> None:
                ctx.arguments(text=pretense.Domain(strategy=lambda: "hello", validator=lambda text: True))
                ctx.raises(ValueError, match="fail")

        real = EchoService()
        test_sm = EchoStateMachine(singletons={EchoService: real})
        test_case_cls = test_sm.to_hypothesis_test_case()
        with self.assertRaises(AssertionError) as cm:
            run_state_machine_as_test(test_case_cls)
        err_msg = str(cm.exception)
        self.assertIn("Return Contract Violation", err_msg)
        self.assertIn("was declared with ctx.raises(ValueError)", err_msg)
        self.assertIn("produced a return value Value('hello') instead of raising", err_msg)

    def test_transition_context_type_checking_with_pyright(self) -> None:
        """Verify that Pyright catches attribute typos and type errors on TransitionContext lambdas."""
        import subprocess
        import tempfile

        invalid_code = '''
from pretense import TransitionContext

class Version:
    major: int
    is_prerelease: bool

class VersionRange:
    text: str

class SUT:
    def check(self, v: Version, r: VersionRange) -> bool: ...

ctx: TransitionContext[SUT, [Version, VersionRange], bool] = TransitionContext()

# Invalid attribute 'pre' instead of 'is_prerelease':
ctx.returns(lambda v, r: v.pre)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py") as f:
            f.write(invalid_code)
            f.flush()
            p = subprocess.run(["uv", "run", "pyright", f.name], capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn('Cannot access attribute "pre"', p.stdout)

        # Invalid return type (string instead of bool)
        invalid_return_type_code = '''
from pretense import TransitionContext

class Version:
    major: int

class VersionRange:
    text: str

class SUT:
    def check(self, v: Version, r: VersionRange) -> bool: ...

ctx: TransitionContext[SUT, [Version, VersionRange], bool] = TransitionContext()

# Invalid return type: 'wrong_type' is not bool
ctx.returns(lambda v, r: "wrong_type")
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py") as f:
            f.write(invalid_return_type_code)
            f.flush()
            p = subprocess.run(["uv", "run", "pyright", f.name], capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("No overloads for \"returns\" match the provided arguments", p.stdout)

        # Invalid attribute in consequent
        invalid_consequent_code = '''
from pretense import TransitionContext

class Version:
    major: int

class VersionRange:
    text: str

class SUT:
    def check(self, v: Version, r: VersionRange) -> bool: ...

ctx: TransitionContext[SUT, [Version, VersionRange], bool] = TransitionContext()

# Invalid attribute in consequent
ctx.consequent(lambda res, v, r: v.invalid_field)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py") as f:
            f.write(invalid_consequent_code)
            f.flush()
            p = subprocess.run(["uv", "run", "pyright", f.name], capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn('Cannot access attribute "invalid_field"', p.stdout)

        # Invalid attribute in recognize
        invalid_recognize_code = '''
from pretense import TransitionContext, Domain

class Version:
    major: int

class VersionRange:
    text: str

class SUT:
    def check(self, v: Version, r: VersionRange) -> bool: ...

ctx: TransitionContext[SUT, [Version, VersionRange], bool] = TransitionContext()

# Invalid attribute in validator
d = Domain[Version](strategy=lambda: Version(), validator=lambda v: v.unknown_field == 1)
ctx.arguments(v=d)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py") as f:
            f.write(invalid_recognize_code)
            f.flush()
            p = subprocess.run(["uv", "run", "pyright", f.name], capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn('Cannot access attribute "unknown_field"', p.stdout)

        valid_code = '''
from pretense import TransitionContext

class Version:
    major: int
    is_prerelease: bool

class VersionRange:
    text: str

class SUT:
    def check(self, v: Version, r: VersionRange) -> bool: ...

ctx: TransitionContext[SUT, [Version, VersionRange], bool] = TransitionContext()

# Valid attribute 'is_prerelease':
ctx.returns(lambda v, r: v.is_prerelease)
'''
        with tempfile.NamedTemporaryFile("w", suffix=".py") as f:
            f.write(valid_code)
            f.flush()
            p = subprocess.run(["uv", "run", "pyright", f.name], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, f"Expected 0 errors but got:\n{p.stdout}")

    def test_requires_check_and_mode_b_pattern(self) -> None:
        """Verify Mode B RequiresCheck flag collection and fake rejection diagnostics."""
        chk = pretense.RequiresCheck()
        self.assertTrue(chk.ok)
        self.assertEqual(chk.reasons, [])

        self.assertTrue(chk(True, "all good"))
        self.assertTrue(chk.ok)
        self.assertEqual(chk.reasons, [])

        self.assertFalse(chk(False, "capacity full"))
        self.assertFalse(chk.ok)
        self.assertEqual(chk.reasons, ["capacity full"])

        self.assertFalse(chk(False, "system paused"))
        self.assertFalse(chk.ok)
        self.assertEqual(chk.reasons, ["capacity full", "system paused"])

        class BufferService:
            def push(self, item: str) -> None: ...

        class BufferStateMachine(pretense.StateMachine[dict[str, Any]]):
            def __init__(self) -> None:
                super().__init__(state={"items": ["a", "b"], "max": 2})

            @pretense.transition(BufferService.push)
            def push(self, ctx: pretense.TransitionContext[BufferService, [str], None]) -> None:
                ctx.requires(lambda check: (
                    check(len(self.state["items"]) < self.state["max"], "buffer capacity reached"),
                ))
                ctx.arguments(item=pretense.Domain(strategy=lambda: "item", validator=lambda item: True))
                ctx.returns(lambda item: None)
                ctx.update(lambda res, item: self.state["items"].append(item))

        sm = BufferStateMachine()
        fake = sm.as_fake(BufferService)
        # Buffer is already full (len 2 == max 2); push should be rejected with reasons
        with self.assertRaises(pretense.NoMatchingTransitionError) as cm:
            fake.push("c")
        self.assertIn("buffer capacity reached", str(cm.exception))

    def test_ensures_check_assertions_and_diffs(self) -> None:
        """Verify EnsuresCheck assertions, formatted diffs, and singleton lookup."""
        class ServiceA:
            def name(self) -> str:
                return "Alpha"

        class ServiceB:
            def name(self) -> str:
                return "Beta"

        inst_a = ServiceA()
        inst_b = ServiceB()
        chk = pretense.EnsuresCheck({ServiceA: inst_a, ServiceB: inst_b})

        # Basic condition assertion
        chk(True, "should pass")
        with self.assertRaises(AssertionError) as cm:
            chk(False, "condition violated")
        self.assertIn("condition violated", str(cm.exception))

        # Equality assertion with diff formatting
        chk.equal(10, 10, "numbers match")
        with self.assertRaises(AssertionError) as cm:
            chk.equal("actual_val", "expected_val", "values mismatch")
        self.assertIn("values mismatch", str(cm.exception))
        self.assertIn("Expected 'expected_val', but got 'actual_val'", str(cm.exception))

        # Singleton resolution
        self.assertIs(chk.get(ServiceA), inst_a)
        self.assertIs(chk.get(ServiceB), inst_b)

        class UnknownService:
            pass

        with self.assertRaises(KeyError):
            chk.get(UnknownService)

    def test_first_class_ensures_and_update_lifecycle(self) -> None:
        """Verify ensures execution during real tests and omission during fake simulation."""
        from dataclasses import dataclass, field

        @dataclass
        class StoreState:
            entries: dict[str, int] = field(default_factory=dict)

        class RealStore:
            def __init__(self) -> None:
                self.data: dict[str, int] = {}

            def put(self, key: str, val: int) -> int:
                self.data[key] = val
                return val

            def get(self, key: str) -> int:
                return self.data.get(key, 0)

        class StoreStateMachine(pretense.StateMachine[StoreState]):
            def __init__(
                self,
                state: Optional[StoreState] = None,
                singletons: Optional[dict[type[Any], Any]] = None,
            ) -> None:
                super().__init__(state=state or StoreState(), singletons=singletons)

            @pretense.transition(RealStore.put)
            def put(self, ctx: pretense.TransitionContext[RealStore, [str, int], int]) -> None:
                ctx.requires(lambda check: check(len(self.state.entries) < 100, "under max capacity"))
                ctx.arguments(
                    key=pretense.Domain.text(min_size=1, max_size=10),
                    val=pretense.Domain.range(0, 1000),
                )
                ctx.returns(lambda key, val: val)
                ctx.ensures(lambda res, store, check, key, val: (
                    check(store is not None, "Real store must be provided to ensures"),
                    check.equal(store.get(key), val, "Store must reflect put value immediately"),
                    check.equal(res, val, "Return value must equal put value"),
                ))
                ctx.update(lambda res, key, val: self.state.entries.__setitem__(key, val))

        # 1. Fake Mode: ensures is omitted!
        sm_fake = StoreStateMachine()
        fake_store = sm_fake.as_fake(RealStore)
        ret = fake_store.put("alpha", 123)
        self.assertEqual(ret, 123)
        self.assertEqual(sm_fake.state.entries["alpha"], 123)

        # 2. Real Mode: ensures is evaluated on the real SUT!
        real_store = RealStore()
        sm_real = StoreStateMachine(singletons={RealStore: real_store})
        ret = sm_real.dispatch_transition("put", "beta", 456)
        self.assertEqual(ret, 456)
        self.assertEqual(real_store.get("beta"), 456)
        self.assertEqual(sm_real.state.entries["beta"], 456)

        # 3. Real Mode with Defective Implementation: ensures catches contract violation!
        class DefectiveStore(RealStore):
            def put(self, key: str, val: int) -> int:
                # Intentionally buggy: does not write to self.data
                return val

        defective_store = DefectiveStore()
        sm_defective = StoreStateMachine(singletons={RealStore: defective_store})
        with self.assertRaises(AssertionError) as cm:
            sm_defective.dispatch_transition("put", "gamma", 789)
        self.assertIn("Store must reflect put value immediately", str(cm.exception))

        # 4. Hypothesis Stateful Fuzzing with ensures:
        fuzz_real = RealStore()
        fuzz_sm = StoreStateMachine(singletons={RealStore: fuzz_real})
        test_case_cls = fuzz_sm.to_hypothesis_test_case()
        run_state_machine_as_test(test_case_cls)

    def test_pretense_engine_singleton(self) -> None:
        """Verify PretenseEngine service registration and basic capabilities."""
        with enter_phase(system):
            engine = get_singleton(pretense.PretenseEngine)
            self.assertIsNotNone(engine)

            config = pretense.PretenseRunnerConfig(
                target_paths=["non_existent_path_to_trigger_empty_discovery"],
                fuzz=False,
                cov=False,
            )
            result = engine.run_suite(config)
            self.assertFalse(result.is_passing)
            self.assertEqual(result.failed, 1)

    def test_pretense_cli_loading_error_and_empty_discovery(self) -> None:
        """Verify CLI exits non-zero on module import error and empty targets."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Broken import test file
            broken_file = Path(tmpdir) / "broken_pretense.py"
            broken_file.write_text("from non_existent_pkg import something\n", encoding="utf-8")
            exit_code = run_pretense_cli([str(broken_file)])
            self.assertNotEqual(exit_code, 0)

            # 2. Empty directory (no test targets)
            empty_dir = Path(tmpdir) / "empty_dir"
            empty_dir.mkdir()
            exit_code = run_pretense_cli([str(empty_dir)])
            self.assertNotEqual(exit_code, 0)

            # 3. Valid test file
            valid_file = Path(tmpdir) / "valid_pretense.py"
            valid_file.write_text(
                "import unittest\n"
                "class DummyTest(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            exit_code = run_pretense_cli([str(valid_file), "--no-fuzz"])
            self.assertEqual(exit_code, 0)

            # 4. Multi-failure test file verifying non-masked failure reporting
            import io
            from contextlib import redirect_stdout
            multi_fail_file = Path(tmpdir) / "multi_fail_pretense.py"
            multi_fail_file.write_text(
                "import unittest\n"
                "class MultiFailTest(unittest.TestCase):\n"
                "    def test_first_failure(self):\n"
                "        self.assertEqual(1, 2, 'First failure msg')\n"
                "    def test_second_failure(self):\n"
                "        self.assertEqual(3, 4, 'Second failure msg')\n",
                encoding="utf-8",
            )
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = run_pretense_cli([str(multi_fail_file), "--no-fuzz"])
            self.assertEqual(exit_code, 1)
            output_str = out.getvalue()
            self.assertIn("test_first_failure", output_str)
            self.assertIn("First failure msg", output_str)
            self.assertIn("test_second_failure", output_str)
            self.assertIn("Second failure msg", output_str)

    def test_strategy_as_value_argument_generation(self) -> None:
        """Verify Hypothesis SearchStrategy instances can be passed directly as values in arguments."""
        @dataclass
        class SampleState:
            values: list[Any] = field(default_factory=list)

        class StrategySm(pretense.StateMachine):
            def __init__(self, state: Optional[SampleState] = None) -> None:
                super().__init__(state=state or SampleState())

            @pretense.transition(name="tuple_with_strategies")
            def step_tuple(self, ctx: pretense.TransitionContext) -> None:
                ctx.arguments(
                    num=pretense.Domain(strategy=st.integers(min_value=10, max_value=20), validator=lambda x: isinstance(x, int)),
                    text="fixed_str",
                    flag=st.booleans(),
                )
                ctx.returns(lambda num, text, flag: (num, text, flag))
                ctx.update(lambda res, num, text, flag: self.state.values.append(res))

            @pretense.transition(name="callable_returning_strategies")
            def step_callable(self, ctx: pretense.TransitionContext) -> None:
                ctx.arguments(
                    num=pretense.Domain(strategy=st.integers(min_value=100, max_value=200), validator=lambda x: isinstance(x, int)),
                )
                ctx.returns(lambda num: num * 2)

            @pretense.transition(name="single_strategy_direct")
            def step_single(self, ctx: pretense.TransitionContext) -> None:
                ctx.arguments(
                    num=pretense.Domain(strategy=st.integers(min_value=500, max_value=600), validator=lambda x: isinstance(x, int)),
                )
                ctx.returns(lambda num: num)

            @pretense.transition(name="callable_accepting_draw")
            def step_draw(self, ctx: pretense.TransitionContext) -> None:
                ctx.arguments(
                    num=pretense.Domain(strategy=lambda draw: draw(st.integers(min_value=1000, max_value=2000)), validator=lambda x: isinstance(x, int)),
                    text=pretense.Domain(strategy="drawn", validator=lambda x: x == "drawn"),
                )
                ctx.returns(lambda num, text: (num, text))

        sm = StrategySm()

        # 1. Deterministic/example-based evaluation outside Hypothesis
        res1 = sm.dispatch_transition("tuple_with_strategies")
        self.assertIsInstance(res1[0], int)
        self.assertTrue(10 <= res1[0] <= 20)
        self.assertEqual(res1[1], "fixed_str")
        self.assertIsInstance(res1[2], bool)
        self.assertEqual(len(sm.state.values), 1)

        res2 = sm.dispatch_transition("callable_returning_strategies")
        self.assertIsInstance(res2, int)
        self.assertTrue(200 <= res2 <= 400)

        res3 = sm.dispatch_transition("single_strategy_direct")
        self.assertIsInstance(res3, int)
        self.assertTrue(500 <= res3 <= 600)

        res4 = sm.dispatch_transition("callable_accepting_draw")
        self.assertIsInstance(res4[0], int)
        self.assertTrue(1000 <= res4[0] <= 2000)
        self.assertEqual(res4[1], "drawn")

        # 2. Dynamic evaluation inside with_draw context
        draw_calls = []
        def mock_draw(strat: Any) -> Any:
            draw_calls.append(strat)
            return 99

        with pretense.with_draw(mock_draw):
            sm.dispatch_transition("tuple_with_strategies")
            self.assertGreaterEqual(len(draw_calls), 2)  # Two strategies were drawn

    def test_strategy_as_value_hypothesis_fuzzing(self) -> None:
        """Verify RuleBasedStateMachine fuzzer draws dynamic values from strategies as values."""
        class DynamicCalculator:
            def __init__(self) -> None:
                self.history: list[int] = []

            def compute(self, base: int, multiplier: int) -> int:
                val = base * multiplier
                self.history.append(val)
                return val

        @dataclass
        class CalcState:
            history: list[int] = field(default_factory=list)

        class CalculatorStateMachine(pretense.StateMachine):
            def __init__(self, state: Optional[CalcState] = None, singletons: Optional[dict[type, Any]] = None) -> None:
                super().__init__(state=state or CalcState(), singletons=singletons or {})

            @pretense.transition(DynamicCalculator.compute)
            def step_compute(self, ctx: pretense.TransitionContext) -> None:
                ctx.arguments(
                    b=pretense.Domain.range(-20, 20),
                    m=pretense.Domain.set([1, 2, 3]),
                )
                ctx.returns(lambda b, m: b * m)
                ctx.ensures(lambda res, calc, check, b, m: (
                    check.equal(res, b * m),
                    check.equal(calc.history[-1], res),
                ))
                ctx.update(lambda res, b, m: self.state.history.append(res))

        calc_sut = DynamicCalculator()
        sm = CalculatorStateMachine(singletons={DynamicCalculator: calc_sut})
        test_case = sm.to_hypothesis_test_case(sut_factory=lambda: {DynamicCalculator: calc_sut})
        run_state_machine_as_test(test_case)
        self.assertGreater(len(calc_sut.history), 0)

    def test_domain_primitives(self) -> None:
        """Verify Domain factory methods create valid strategies and analytical validators."""
        # Domain.set
        d_set = pretense.Domain.set(["apple", "banana", "cherry"])
        self.assertTrue(d_set.validate("banana"))
        self.assertFalse(d_set.validate("orange"))

        # Domain.range
        d_range = pretense.Domain.range(1, 10)
        self.assertTrue(d_range.validate(1))
        self.assertTrue(d_range.validate(9))
        self.assertFalse(d_range.validate(0))
        self.assertFalse(d_range.validate(10))
        self.assertFalse(d_range.validate(True))  # bool is subclass of int but must be rejected

        # Domain.regex
        d_re = pretense.Domain.regex(r"^\d{3}-[a-z]{2}$")
        self.assertTrue(d_re.validate("123-ab"))
        self.assertFalse(d_re.validate("12-ab"))
        self.assertFalse(d_re.validate(123))

        # Domain.type
        d_float = pretense.Domain.type(float)
        self.assertTrue(d_float.validate(3.14))
        self.assertFalse(d_float.validate("3.14"))

        # Domain.boolean
        d_bool = pretense.Domain.boolean()
        self.assertTrue(d_bool.validate(True))
        self.assertTrue(d_bool.validate(False))
        self.assertFalse(d_bool.validate(1))

        # Domain.text
        d_text = pretense.Domain.text(min_size=2, max_size=5)
        self.assertTrue(d_text.validate("abc"))
        self.assertFalse(d_text.validate("a"))
        self.assertFalse(d_text.validate("abcdef"))
        self.assertFalse(d_text.validate(123))

    def test_domain_of_coercion(self) -> None:
        """Verify Domain.of coerces native Python constructs."""
        d_set = pretense.Domain.of({"a", "b"})
        self.assertTrue(d_set.validate("a"))
        self.assertFalse(d_set.validate("c"))

        d_rng = pretense.Domain.of(range(5, 10))
        self.assertTrue(d_rng.validate(7))
        self.assertFalse(d_rng.validate(4))

        import re
        d_pat = pretense.Domain.of(re.compile(r"^[A-Z]+$"))
        self.assertTrue(d_pat.validate("HELLO"))
        self.assertFalse(d_pat.validate("hello"))

        d_cls = pretense.Domain.of(int)
        self.assertTrue(d_cls.validate(42))
        self.assertFalse(d_cls.validate("42"))

    def test_domain_required_placeholder(self) -> None:
        """Verify Domain.required generates a type-checking placeholder that fails on evaluation."""
        d_req = pretense.Domain.required("missing_param")
        with self.assertRaises(NotImplementedError) as ctx:
            d_req.validate(123)
        self.assertIn("missing_param", str(ctx.exception))

        with self.assertRaises(NotImplementedError) as ctx2:
            strat_fn = d_req.to_strategy()
            strat_fn()
        self.assertIn("missing_param", str(ctx2.exception))

    def test_domain_perturb(self) -> None:
        """Verify Domain.perturb derives relational mutated values from an anchor."""
        anchor = 10
        d_pert = pretense.Domain.perturb(
            anchor,
            mutations=[
                lambda a: a + 1,
                lambda a: a + 2,
            ],
            validator=lambda val: val in (11, 12),
        )
        self.assertTrue(d_pert.validate(11))
        self.assertTrue(d_pert.validate(12))
        self.assertFalse(d_pert.validate(10))
        self.assertFalse(d_pert.validate(13))

        # Generation resolves mutation
        draw_fn = lambda s: (lambda a: a + 1)
        val = d_pert.strategy(draw_fn)
        self.assertEqual(val, 11)

    def test_dependent_domains_and_fake_adapter_dispatch(self) -> None:
        """Verify dependent domains validate and generate across relational arguments in fake dispatch."""
        class ComparatorProto:
            def is_less(self, a: int, b: int) -> bool: ...

        @dataclass
        class CompState:
            comparisons: list[tuple[int, int]] = field(default_factory=list)

        class ComparatorStateMachine(pretense.StateMachine):
            def __init__(self, state: Optional[CompState] = None, singletons: Optional[dict[type, Any]] = None) -> None:
                super().__init__(state=state or CompState(), singletons=singletons or {})

            @pretense.transition(ComparatorProto.is_less)
            def step_less(self, ctx: pretense.TransitionContext) -> None:
                ctx.arguments(
                    a=pretense.Domain.range(0, 10),
                    b=lambda a: pretense.Domain.range(a + 1, 20),
                )
                ctx.returns(lambda a, b: True)
                ctx.ensures(lambda res, comp, check, a, b: check.equal(res, True))
                ctx.update(lambda res, a, b: self.state.comparisons.append((a, b)))

        class ComparatorSut:
            def __init__(self) -> None:
                self.calls: list[tuple[int, int]] = []

            def is_less(self, a: int, b: int) -> bool:
                self.calls.append((a, b))
                return a < b

        sut = ComparatorSut()
        sm = ComparatorStateMachine(singletons={ComparatorProto: sut})
        fake = sm.as_fake(ComparatorProto)

        # Valid relational call matches and updates state
        res = fake.is_less(3, 8)
        self.assertTrue(res)
        self.assertEqual(sm.state.comparisons, [(3, 8)])

        # Keyword arguments call also matches
        res_kw = fake.is_less(a=2, b=5)
        self.assertTrue(res_kw)
        self.assertEqual(sm.state.comparisons, [(3, 8), (2, 5)])

        # Non-matching relational arguments (b <= a) fail transition lookup
        with self.assertRaises(pretense.NoMatchingTransitionError):
            fake.is_less(5, 2)

        with self.assertRaises(pretense.NoMatchingTransitionError):
            fake.is_less(5, 5)

        # Fuzzing test case generation executes cleanly
        test_case = sm.to_hypothesis_test_case(sut_factory=lambda: {ComparatorProto: sut})
        run_state_machine_as_test(test_case)
        self.assertGreater(len(sut.calls), 0)


if __name__ == "__main__":
    unittest.main()

