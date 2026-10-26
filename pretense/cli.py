"""CLI runner for Pretense state machines (uv run pretense)."""

import argparse
import faulthandler
import importlib.util
import os
import signal
import sys
import threading
import time
import traceback
import unittest
from pathlib import Path
from typing import Any, List, Optional, Tuple

import hypothesis
from hypothesis.stateful import RuleBasedStateMachine

from pretense.proto import StateMachineProto
from pretense.synthesis import synthesize_unit_test


def _configure_sys_path() -> None:
    """Configures sys.path by resolving cwd and pythonpath in pyproject.toml."""
    cwd = Path.cwd().resolve()
    if str(cwd) not in sys.path:
        sys.path.insert(0, str(cwd))

    pyproject = cwd / "pyproject.toml"
    if pyproject.is_file():
        try:
            import tomllib

            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            pytest_paths = (
                data.get("tool", {})
                .get("pytest", {})
                .get("ini_options", {})
                .get("pythonpath", [])
            )
            for p in pytest_paths:
                resolved = (cwd / p).resolve()
                if resolved.is_dir() and str(resolved) not in sys.path:
                    sys.path.append(str(resolved))
        except Exception:
            pass


class PretenseTestTarget:
    """Represents a discovered test target (compiled RuleBasedStateMachine or Proto)."""

    def __init__(
        self,
        name: str,
        file_path: Path,
        test_case_cls: Any,
        proto: Optional[StateMachineProto[Any]] = None,
    ) -> None:
        self.name = name
        self.file_path = file_path
        self.test_case_cls = test_case_cls
        self.proto = proto


def discover_targets(
    paths: List[Path],
    keyword: Optional[str] = None,
    no_fuzz: bool = False,
) -> List[PretenseTestTarget]:
    """Discover state machine test targets across the specified paths."""
    _configure_sys_path()
    discovered_files: List[Path] = []

    for path in paths:
        if path.is_file() and path.suffix == ".py":
            discovered_files.append(path.resolve())
        elif path.is_dir():
            for root, _, files in os.walk(path):
                root_path = Path(root)
                if "pretense" in root_path.parts or any("pretense" in f for f in files):
                    for f in files:
                        if f.endswith(".py") and not f.startswith("__"):
                            discovered_files.append((root_path / f).resolve())

    # De-duplicate while preserving order
    unique_files: List[Path] = []
    seen = set()
    for f in discovered_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    targets: List[PretenseTestTarget] = []

    for file_path in unique_files:
        module_name = f"pretense_dynamic_{file_path.stem}_{abs(hash(str(file_path)))}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            print(f"Warning: Failed to import {file_path}: {e}", file=sys.stderr)
            continue

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            val = getattr(module, attr_name)

            # Check keyword filter
            target_ident = f"{file_path.stem}::{attr_name}"

            # Case 1: Already a compiled RuleBasedStateMachine subclass
            if (
                isinstance(val, type)
                and issubclass(val, RuleBasedStateMachine)
                and val is not RuleBasedStateMachine
            ):
                if no_fuzz:
                    continue
                if not keyword or keyword.lower() in target_ident.lower():
                    targets.append(PretenseTestTarget(target_ident, file_path, val))

            # Case 2: unittest.TestCase subclass
            elif isinstance(val, type) and issubclass(val, unittest.TestCase):
                for m in dir(val):
                    if m.startswith("test_") and callable(getattr(val, m)):
                        sub_ident = f"{file_path.stem}::{attr_name}::{m}"
                        if no_fuzz and ("fuzz" in sub_ident.lower() or hasattr(getattr(val, m), "_hypothesis_internal_use_seed")):
                            continue
                        if not keyword or keyword.lower() in sub_ident.lower():
                            targets.append(PretenseTestTarget(sub_ident, file_path, (val, m)))

            # Case 3: Standard test function
            elif callable(val) and attr_name.startswith("test_") and not isinstance(val, type):
                if no_fuzz and "fuzz" in target_ident.lower():
                    continue
                if not keyword or keyword.lower() in target_ident.lower():
                    targets.append(PretenseTestTarget(target_ident, file_path, val))

    return targets


def run_target(
    target: PretenseTestTarget,
    max_examples: int,
    seed: Optional[int],
    verbose: bool,
    timeout: Optional[float] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Execute a single Pretense test target and return (passed, error_msg, synthesized_test)."""
    timer: Optional[threading.Timer] = None
    if timeout is not None and timeout > 0.0:
        try:
            faulthandler.dump_traceback_later(timeout, exit=True, file=sys.stderr)
        except Exception:
            pass

        if timeout > 0.4:
            def _warn() -> None:
                sys.stderr.write(
                    f"\n[FAIL] Pretense target '{target.name}' execution timed out after {timeout:.1f}s "
                    f"(possible infinite loop or deadlock detected in code under test).\n"
                )
                try:
                    from pretense.compiler import format_active_step_diagnostic
                    diag = format_active_step_diagnostic()
                    if diag:
                        sys.stderr.write(f"{diag}\n")
                except Exception:
                    pass
                sys.stderr.write("Thread stack trace at timeout:\n")
                sys.stderr.flush()

            timer = threading.Timer(timeout - 0.2, _warn)
            timer.daemon = True
            timer.start()

    try:
        if isinstance(target.test_case_cls, type) and issubclass(target.test_case_cls, RuleBasedStateMachine):
            settings_kwargs: dict[str, Any] = {
                "max_examples": max_examples,
                "deadline": None,
            }
            if seed is not None:
                settings_kwargs["derandomize"] = True

            hyp_settings_fn: Any = getattr(hypothesis, "settings")
            cfg = hyp_settings_fn(**settings_kwargs)

            target.test_case_cls.TestCase.settings = cfg
            tc_instance = target.test_case_cls.TestCase("runTest")

            try:
                tc_instance.runTest()
                return True, None, None
            except Exception as e:
                err_buf = traceback.format_exc()
                synthesized = None
                last_trace = getattr(target.test_case_cls, "_last_trace", None)
                if last_trace:
                    synthesized = synthesize_unit_test(
                        test_name=f"test_reproduce_{target.name.replace('::', '_')}",
                        proto_class_name="proto",
                        state_class_name="DAGState",
                        steps=last_trace,
                        failure_critique=str(e),
                    )
                return False, err_buf, synthesized

        elif isinstance(target.test_case_cls, tuple) and len(target.test_case_cls) == 2:
            cls, method_name = target.test_case_cls
            suite = unittest.TestSuite()
            suite.addTest(cls(method_name))
            result = unittest.TestResult()
            suite.run(result)
            if result.wasSuccessful():
                return True, None, None
            err_msg = ""
            for _, err in result.errors:
                err_msg += err + "\n"
            for _, fail in result.failures:
                err_msg += fail + "\n"
            return False, err_msg.strip(), None

        elif callable(target.test_case_cls):
            # Direct function execution
            try:
                target.test_case_cls()
                return True, None, None
            except Exception as e:
                return False, traceback.format_exc(), None

        return False, f"Target {target.name} is not a valid test runner", None
    finally:
        if timer is not None:
            timer.cancel()
        if timeout is not None and timeout > 0.0:
            try:
                faulthandler.cancel_dump_traceback_later()
            except Exception:
                pass


def _setup_timeout_and_signal_handlers() -> None:
    """Configures faulthandler and SIGTERM handlers to surface active transitions on timeout."""
    try:
        faulthandler.enable(file=sys.stderr)
    except Exception:
        pass

    def _sigterm_handler(signum: int, frame: Any) -> None:
        from pretense.compiler import format_active_step_diagnostic

        sys.stderr.write("\n[TIMEOUT / SIGTERM DETECTED IN PRETENSE RUNNER]\n")
        try:
            diag = format_active_step_diagnostic()
            if diag:
                sys.stderr.write(f"{diag}\n")
        except Exception:
            pass
        sys.stderr.write("Thread stack trace at signal:\n")
        sys.stderr.flush()
        try:
            faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
        except Exception:
            pass
        sys.exit(143)

    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, _sigterm_handler)
        except (ValueError, OSError):
            pass


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint for Pretense."""
    _setup_timeout_and_signal_handlers()
    parser = argparse.ArgumentParser(
        prog="pretense",
        description="Pretense: Unified State-Machine Verification & Fake Synthesis Engine",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Directories or files to discover state machines in (default: current directory)",
    )
    parser.add_argument(
        "-k",
        "--keyword",
        help="Only run tests whose names or file paths match the given keyword expression",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Increase output verbosity",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Quiet output",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=50,
        help="Maximum examples per state machine to explore in Hypothesis (default: 50)",
    )
    parser.add_argument(
        "--no-fuzz",
        action="store_true",
        help="Only run deterministic unit and parity tests, skipping fuzz tests and state machine exploration",
    )
    parser.add_argument(
        "--cov",
        nargs="?",
        const="",
        default=None,
        help="Evaluate and report statement code coverage for the specified source file or matching impl.py",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Minimum required code coverage percentage (fails if coverage is below threshold)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Deterministic PRNG seed for reproducible test replay",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Per-target execution timeout in seconds (default: 30.0s, or 0 to disable; respects PRETENSE_TIMEOUT or CLEANROOM_VERIFY_TIMEOUT)",
    )

    args = parser.parse_args(argv)

    target_timeout = args.timeout
    if target_timeout is None:
        env_val = os.environ.get("PRETENSE_TIMEOUT") or os.environ.get("CLEANROOM_VERIFY_TIMEOUT")
        if env_val:
            try:
                target_timeout = float(env_val)
            except ValueError:
                target_timeout = 30.0
        else:
            target_timeout = 30.0
    if target_timeout is not None and target_timeout <= 0.0:
        target_timeout = None

    search_paths = [Path(p) for p in args.paths]
    cov = None
    if args.cov is not None:
        try:
            import coverage
            include_patterns = []
            if args.cov != "":
                include_patterns = [f"*{args.cov}*"]
            else:
                for p in search_paths:
                    p_res = p.resolve()
                    if p_res.is_file() and "pretense" in p_res.parts:
                        cand_name = p_res.stem.replace("_pretense", ".py")
                        include_patterns.append(f"*{cand_name}")
                    elif p_res.is_dir():
                        if p_res.name == "pretense" and (p_res.parent / "lib").is_dir():
                            for f in (p_res.parent / "lib").glob("*.py"):
                                if not f.name.startswith("__"):
                                    include_patterns.append(f"*{f.name}")
                        for root, _, files in os.walk(p_res):
                            if Path(root).name == "lib":
                                for f in files:
                                    if f.endswith(".py") and not f.startswith("__"):
                                        include_patterns.append(f"*{f}")
            cov = coverage.Coverage(include=include_patterns if include_patterns else ["*lib/*.py"])
            cov.start()
        except ImportError:
            print("Warning: coverage package is not installed; running without coverage.", file=sys.stderr)

    targets = discover_targets(search_paths, keyword=args.keyword, no_fuzz=args.no_fuzz)

    if not targets:
        if cov is not None:
            cov.stop()
        print("No Pretense state machine targets discovered.")
        return 0

    print(f"=== Pretense Test Runner: Discovered {len(targets)} targets ===")
    start_time = time.time()
    passed_count = 0
    failed_count = 0

    for target in targets:
        if args.verbose:
            sys.stdout.write(f"Running {target.name} ... ")
            sys.stdout.flush()

        passed, err, synth = run_target(
            target,
            max_examples=args.max_examples,
            seed=args.seed,
            verbose=args.verbose,
            timeout=target_timeout,
        )

        if passed:
            passed_count += 1
            if args.verbose:
                print("PASSED")
            elif not args.quiet:
                sys.stdout.write(".")
                sys.stdout.flush()
        else:
            failed_count += 1
            if args.verbose:
                print("FAILED")
            elif not args.quiet:
                sys.stdout.write("F")
                sys.stdout.flush()

            print(f"\n\n{'='*70}\nFAIL: {target.name}\n{'-'*70}")
            if err:
                print(err)
            if synth:
                print(f"\n{'-'*70}\nSYNTHESIZED DETERMINISTIC REGRESSION TEST:\n{'-'*70}")
                print(synth)
                print(f"{'='*70}\n")

    if not args.verbose and not args.quiet:
        print("")

    elapsed = time.time() - start_time
    print(f"\n=== {passed_count} passed, {failed_count} failed in {elapsed:.2f}s ===")

    try:
        faulthandler.cancel_dump_traceback_later()
    except Exception:
        pass

    if cov is not None:
        cov.stop()
        cov.save()
        print("\n=== Pretense Code Coverage Report ===")
        total_cov = cov.report(show_missing=True)
        if args.threshold is not None and total_cov < args.threshold:
            print(
                f"\nCoverage deficit: {total_cov:.1f}% is below required threshold {args.threshold:.1f}%.",
                file=sys.stderr,
            )
            return 1

    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
