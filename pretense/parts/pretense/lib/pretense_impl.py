"""Pretense runtime engine implementation, Hypothesis compiler, watchdog, and CLI."""

from __future__ import annotations

import argparse
import copy
import faulthandler
import importlib.util
import os
import re
import signal
import sys
import threading
import time
import traceback
import unittest
from pathlib import Path
import tomllib
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
)

import hypothesis
import hypothesis.strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    SystemTier,
    get_default_registry,
    system,
)
from . import pretense
from .pretense import (
    NotBound,
    Outcome,
    PretenseRunResult,
    PretenseRunnerConfig,
    PretenseSpecificationError,
    Raised,
    StateMachineProto,
    TraceStep,
    Value,
)

# Active step journaling for diagnostic and timeout reporting
_ACTIVE_STEP: Optional[TraceStep] = None
_ACTIVE_TRACE: List[TraceStep] = []


def get_active_step() -> Optional[TraceStep]:
    """Returns the currently executing trace step, if any."""
    return _ACTIVE_STEP


def get_active_trace() -> List[TraceStep]:
    """Returns the trace of steps leading up to and including the current step."""
    return list(_ACTIVE_TRACE)


def format_active_step_diagnostic(
    prefix: str = "Active Step at failure",
    target_name: Optional[str] = None,
) -> Optional[str]:
    """Formats a diagnostic string detailing the active and preceding steps during a timeout."""
    global _ACTIVE_STEP, _ACTIVE_TRACE
    if _ACTIVE_STEP is None:
        return None
    target_info = f" in target '{target_name}'" if target_name else ""
    lines = [
        f"{prefix}{target_info}:",
        f"  Active Pretense Transition: '{_ACTIVE_STEP.transition_name}' (method: {_ACTIVE_STEP.target_name or '<seeding>'})",
        f"  Arguments: {_ACTIVE_STEP.args!r}",
    ]
    if len(_ACTIVE_TRACE) > 1:
        lines.append(f"  Preceding Steps ({len(_ACTIVE_TRACE) - 1}):")
        for i, step in enumerate(_ACTIVE_TRACE[:-1], 1):
            args_str = ", ".join(repr(a) for a in step.args)
            lines.append(f"    {i}. {step.transition_name}({args_str})")
    return "\n".join(lines)


class ActiveStepTracker:
    """Tracks active transition steps and state snapshots for diagnostics."""

    @staticmethod
    def get_active_step() -> Optional[Tuple[str, Tuple[Any, ...], Mapping[str, Any]]]:
        step = get_active_step()
        if step is None:
            return None
        return (step.transition_name, step.args, step.kwargs)

    @staticmethod
    def format_active_step_diagnostic(
        prefix: str = "Active Step at failure",
        target_name: Optional[str] = None,
    ) -> str:
        res = format_active_step_diagnostic(prefix, target_name)
        return res or ""


class WatchdogMonitor:
    """Coordinates execution watchdogs using software timers and faulthandler alarms."""

    @staticmethod
    def resolve_timeout(default: float = 45.0) -> float:
        """Resolves watchdog execution timeout dynamically from environment variables."""
        if "PRETENSE_TIMEOUT" in os.environ:
            try:
                return float(os.environ["PRETENSE_TIMEOUT"].strip())
            except ValueError:
                pass
        if "AUTOFAB_WATCHDOG_TIMEOUT" in os.environ:
            try:
                return float(os.environ["AUTOFAB_WATCHDOG_TIMEOUT"].strip())
            except ValueError:
                pass
        for env_key in ("AUTOFAB_VERIFY_TIMEOUT", "CLEANROOM_VERIFY_TIMEOUT"):
            if env_key in os.environ:
                try:
                    outer = float(os.environ[env_key].strip())
                    return max(5.0, outer - 10.0)
                except ValueError:
                    pass
        return default

    @staticmethod
    def arm(timeout_seconds: float, target_name: Optional[str] = None) -> Any:
        if timeout_seconds <= 0:
            return None

        try:
            faulthandler.dump_traceback_later(
                timeout_seconds, exit=True, file=sys.stderr
            )
        except (ValueError, OSError, RuntimeError):
            pass

        warning_delay = (
            max(0.2, timeout_seconds - 0.2)
            if timeout_seconds > 0.4
            else timeout_seconds * 0.8
        )
        timer: Optional[threading.Timer] = None

        def _hard_kill() -> None:
            time.sleep(2.0)
            os._exit(1)

        def _timeout_warning() -> None:
            target_str = f"'{target_name}' " if target_name else ""
            sys.stderr.write(
                f"\n[FAIL] Pretense target {target_str}execution timed out after {timeout_seconds:.1f}s "
                f"(possible infinite loop or deadlock detected in code under test).\n"
            )
            diag = format_active_step_diagnostic(
                "ACTIVE STEP DIAGNOSTIC (PRE-TIMEOUT WARNING)", target_name
            )
            if diag:
                sys.stderr.write(f"{diag}\n")
            sys.stderr.write("Thread stack trace at timeout:\n")
            sys.stderr.flush()
            killer = threading.Thread(target=_hard_kill, daemon=True)
            killer.start()
            try:
                import _thread
                _thread.interrupt_main()
            except Exception:
                pass

        timer = threading.Timer(warning_delay, _timeout_warning)
        timer.daemon = True
        timer.start()

        return (timer, timeout_seconds)

    @staticmethod
    def disarm(handle: Any) -> None:
        if handle is None:
            return
        timer, _ = handle
        if timer is not None:
            timer.cancel()
        try:
            faulthandler.cancel_dump_traceback_later()
        except (ValueError, OSError, RuntimeError):
            pass


def _invoke_target(sut: Any, target_fn: Any, args: tuple[Any, ...]) -> Any:
    target_name = getattr(target_fn, "__name__", "")
    target_qualname = getattr(target_fn, "__qualname__", "")
    class_qualname = target_qualname.rsplit(".", 1)[0] if "." in target_qualname else ""

    # If SUT is a dict of singletons (e.g. {DAG: dag_instance, WaveScheduler: ws_instance})
    if isinstance(sut, dict):
        if class_qualname:
            for target_type, instance in sut.items():
                t_name = getattr(target_type, "__name__", "")
                t_qual = getattr(target_type, "__qualname__", "")
                if t_name == class_qualname or t_qual == class_qualname:
                    if hasattr(instance, target_name):
                        attr = getattr(instance, target_name)
                        if callable(attr):
                            return attr(*args)

        for instance in sut.values():
            if instance is not None and hasattr(instance, target_name):
                attr = getattr(instance, target_name)
                if callable(attr):
                    return attr(*args)

    candidates: List[Any] = []
    if isinstance(sut, dict):
        candidates.extend(sut.values())
    elif hasattr(sut, "__dict__"):
        candidates.append(sut)
        candidates.extend(vars(sut).values())
    else:
        candidates.append(sut)

    for cand in candidates:
        if cand is not None and hasattr(cand, target_name):
            attr = getattr(cand, target_name)
            if callable(attr):
                return attr(*args)

    return target_fn(sut, *args)


def compile_hypothesis_test_case(
    proto: Any,
    sut_factory: Optional[Any] = None,
    initial_state_factory: Optional[Any] = None,
    settings: Optional[Any] = None,
    name: Optional[str] = None,
    collaborators: Optional[Sequence[Any]] = None,
) -> Type[Any]:
    """Compile a StateMachine or StateMachineProto into an executable Hypothesis test case."""
    proto_inst = proto() if isinstance(proto, type) else proto
    class_name = name or f"TestPretense{proto_inst.__class__.__name__}"

    collab_list: List[Any] = list(collaborators or [])
    if hasattr(proto_inst, "collaborators") and proto_inst.collaborators:
        for c in proto_inst.collaborators:
            if c not in collab_list:
                collab_list.append(c)
    if hasattr(proto_inst, "collaborator_types") and proto_inst.collaborator_types:
        for c in proto_inst.collaborator_types:
            if c not in collab_list:
                collab_list.append(c)

    class _DummyData:
        def draw(self, strategy: Any) -> Any:
            return strategy.example() if hasattr(strategy, "example") else None

    def make_rule_method(t: Any) -> Callable[..., Any]:
        @rule(data=st.data())
        def rule_method(
            self: Any, data: Any = None, *call_args: Any, **call_kwargs: Any
        ) -> Any:
            if data is None:
                data = _DummyData()
            curr_t = t
            if hasattr(self.sm, "transitions"):
                for candidate in self.sm.transitions:
                    if candidate.name == t.name:
                        curr_t = candidate
                        break

            s_dict: Dict[Any, Any] = {}
            if isinstance(self.sut, dict):
                s_dict.update(self.sut)
            elif self.sut is not None:
                s_dict[type(self.sut)] = self.sut
            if hasattr(self.sm, "singletons") and isinstance(self.sm.singletons, dict):
                s_dict.update(self.sm.singletons)
            try:
                from support.lib.lifecycle import get_active_scope

                scope = get_active_scope()
                instances_by_desc = getattr(scope, "_instances_by_desc", None)
                if instances_by_desc is not None and isinstance(
                    instances_by_desc, dict
                ):
                    for inst in instances_by_desc.values():
                        if inst not in s_dict.values():
                            s_dict[type(inst)] = inst
            except Exception:
                pass

            from .pretense import (
                with_draw,
                UnsatisfiedAntecedentError,
                _ACTIVE_SUTS,
                _current_sut,
                _is_verification,
                _current_target,
                _current_method,
                _current_args,
                _current_kwargs,
                _current_sm,
                _last_contracted_exception_type,
            )

            token_suts = _ACTIVE_SUTS.set(dict(s_dict))
            token_sut = _current_sut.set(self.sut)
            token_sm = _current_sm.set(self.sm)

            if getattr(curr_t, "is_seeding", False):
                is_fake = getattr(self.sut, "__is_pretense_fake__", False)
                if not is_fake:
                    # In implementation testing, the target's own seeding transitions are suppressed.
                    # Only seeding transitions on collaborator fakes (in s_dict) are permitted.
                    is_collab_seeding = False
                    for inst in s_dict.values():
                        if (
                            inst is not self.sut
                            and getattr(inst, "__is_pretense_fake__", False)
                            and hasattr(inst, curr_t.name)
                        ):
                            is_collab_seeding = True
                            break
                    if not is_collab_seeding:
                        _current_sm.reset(token_sm)
                        _current_sut.reset(token_sut)
                        _ACTIVE_SUTS.reset(token_suts)
                        return None

            if not all(req(self.sm.state, self.sm) for req in curr_t.requirements):
                _current_sm.reset(token_sm)
                _current_sut.reset(token_sut)
                _ACTIVE_SUTS.reset(token_suts)
                return None

            if call_args or call_kwargs:
                if curr_t.args_fn is not None:
                    args = curr_t.args_fn(
                        self.sm.state, self.sm, *call_args, **call_kwargs
                    )
                else:
                    args = call_args or tuple(call_kwargs.values())
            else:
                with with_draw(data.draw):
                    if curr_t.args_fn is not None:
                        import inspect

                        sig = inspect.signature(curr_t.args_fn)
                        extra_params = [
                            p
                            for p in list(sig.parameters.values())[2:]
                            if p.kind
                            in (
                                inspect.Parameter.POSITIONAL_ONLY,
                                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                            )
                        ]
                        nb_args = [NotBound] * len(extra_params)
                        try:
                            args = curr_t.args_fn(self.sm.state, self.sm, *nb_args)
                        except UnsatisfiedAntecedentError:
                            _current_sm.reset(token_sm)
                            _current_sut.reset(token_sut)
                            _ACTIVE_SUTS.reset(token_suts)
                            return None
                    else:
                        args = ()

            if args is None:
                print("DEBUG: args is None!")
                _current_sm.reset(token_sm)
                _current_sut.reset(token_sut)
                _ACTIVE_SUTS.reset(token_suts)
                return None

            global _ACTIVE_STEP, _ACTIVE_TRACE
            current_step = TraceStep(
                curr_t.name,
                getattr(curr_t.target, "__name__", None),
                getattr(curr_t, "is_seeding", False),
                args,
                {},
                None,
            )
            self.trace.append(current_step)
            type(self)._last_trace = list(self.trace)
            _ACTIVE_STEP = current_step
            _ACTIVE_TRACE = list(self.trace)

            target_name = getattr(curr_t.target, "__name__", curr_t.name)
            is_fake = getattr(self.sut, "__is_pretense_fake__", False)
            token_ver = _is_verification.set(not is_fake)
            token_tgt = _current_target.set(self.sut)
            token_mth = _current_method.set(target_name)
            token_arg = _current_args.set(args)
            token_kw = _current_kwargs.set({})
            token_exc_type = _last_contracted_exception_type.set(None)

            try:
                res = None
                if getattr(curr_t, "is_seeding", False):
                    seeding_target = None
                    if hasattr(self.sut, curr_t.name):
                        seeding_target = self.sut
                    else:
                        for inst in s_dict.values():
                            if hasattr(inst, curr_t.name):
                                seeding_target = inst
                                break
                    if seeding_target is not None and (
                        getattr(curr_t, "_target_fn", None) is None
                        or getattr(seeding_target, "__is_pretense_fake__", False)
                    ):
                        res = getattr(seeding_target, curr_t.name)(*args)
                    elif getattr(curr_t, "_target_fn", None) is not None:
                        res = curr_t._target_fn(self.sm, *args)
                    else:
                        if curr_t.return_fn is not None:
                            res = curr_t.return_fn(self.sm.state, self.sm, *args)
                        if curr_t.provider is not None:
                            curr_t.provider(self.sm.state, self.sm, *args, result=res)
                elif getattr(curr_t, "_target_fn", None) is not None:
                    res = curr_t._target_fn(self.sm, *args)
                    exp_type = _last_contracted_exception_type.get()
                    if exp_type is not None:
                        _last_contracted_exception_type.set(None)
                        raise AssertionError(
                            f"Contracted Operational Exception Missing: Transition '{curr_t.name}' was expected to raise "
                            f"'{exp_type.__name__}' because require_env condition was violated, but SUT produced "
                            f"outcome {res!r} instead."
                        )
                else:
                    sut_exc: Optional[Exception] = None
                    sut_res: Any = None
                    try:
                        sut_res = _invoke_target(self.sut, curr_t.target, args)
                    except Exception as e:
                        sut_exc = e

                    sut_outcome = (
                        Raised(sut_exc) if sut_exc is not None else Value(sut_res)
                    )
                    valid_outcome: Any = None
                    if curr_t.return_fn is not None:
                        recognized = curr_t.return_fn(
                            self.sm.state, self.sm, *args, outcome=sut_outcome
                        )
                        if recognized is None and sut_outcome == Value(None):
                            valid_outcome = Value(None)
                        elif recognized is not None:
                            valid_outcome = (
                                recognized
                                if isinstance(recognized, (Value, Raised))
                                else Value(recognized)
                            )
                        else:
                            reason = ""
                            ctx_obj = getattr(curr_t, "ctx", None)
                            if (
                                ctx_obj
                                and getattr(ctx_obj, "expected_exception", None)
                                is not None
                            ):
                                exp_cls, exp_m = ctx_obj.expected_exception
                                reason = (
                                    f" (transition '{curr_t.name}' was declared with ctx.raises({exp_cls.__name__}) "
                                    f"expecting an exception, but SUT produced a return value {sut_outcome!r} instead of raising; "
                                    f"ctx.raises and ctx.returns are mutually exclusive)"
                                )
                            raise AssertionError(
                                f"Return Contract Violation: SUT produced invalid outcome {sut_outcome!r} "
                                f"which was rejected by the returns recognizer for '{curr_t.name}'{reason}"
                            )
                    else:
                        if sut_exc is not None:
                            raise sut_exc
                        valid_outcome = Value(sut_res)

                    actual_val = (
                        valid_outcome.val
                        if isinstance(valid_outcome, Value)
                        else valid_outcome
                    )
                    from .pretense import EnsuresCheck, _resolve_target_singleton

                    target_obj = _resolve_target_singleton(s_dict, curr_t.target)
                    if target_obj is None and self.sut is not None:
                        if isinstance(self.sut, dict):
                            target_obj = (
                                next(iter(self.sut.values())) if self.sut else None
                            )
                        else:
                            target_obj = self.sut
                    if getattr(curr_t, "ensure_fn", None) is not None:
                        check_obj = EnsuresCheck(s_dict)
                        curr_t.ensure_fn(actual_val, target_obj, check_obj, *args)
                    if curr_t.provider is not None:
                        curr_t.provider(
                            self.sm.state, self.sm, *args, result=actual_val
                        )
                    res = actual_val
                current_step = TraceStep(
                    curr_t.name,
                    getattr(curr_t.target, "__name__", None),
                    getattr(curr_t, "is_seeding", False),
                    args,
                    {},
                    res,
                )
                self.trace[-1] = current_step
            except AssertionError:
                raise
            except BaseException as e:
                exp_type = _last_contracted_exception_type.get()
                if exp_type is not None and isinstance(e, exp_type):
                    _last_contracted_exception_type.set(None)
                    current_step = TraceStep(
                        curr_t.name,
                        getattr(curr_t.target, "__name__", None),
                        getattr(curr_t, "is_seeding", False),
                        args,
                        {},
                        None,
                    )
                    self.trace[-1] = current_step
                else:
                    raise
            finally:
                _ACTIVE_STEP = None
                _last_contracted_exception_type.reset(token_exc_type)
                _current_sm.reset(token_sm)
                _current_kwargs.reset(token_kw)
                _current_args.reset(token_arg)
                _current_method.reset(token_mth)
                _current_target.reset(token_tgt)
                _is_verification.reset(token_ver)
                _current_sut.reset(token_sut)
                _ACTIVE_SUTS.reset(token_suts)

            self.sm.check_invariants()

        rule_method.__name__ = f"step_{t.name}"
        return rule_method

    def make_collab_rule_method(c_spec: Any, ct: Any) -> Callable[..., Any]:
        c_proto = c_spec() if isinstance(c_spec, type) else c_spec

        @rule(data=st.data())
        def collab_rule_method(
            self: Any, data: Any = None, *call_args: Any, **call_kwargs: Any
        ) -> Any:
            if data is None:
                data = _DummyData()
            from .pretense import (
                with_draw,
                UnsatisfiedAntecedentError,
                _ACTIVE_SUTS,
                _current_sut,
                _is_verification,
                _current_target,
                _current_method,
                _current_args,
                _current_kwargs,
                _current_sm,
                _last_contracted_exception_type,
            )

            s_dict: Dict[Any, Any] = {}
            if isinstance(self.sut, dict):
                s_dict.update(self.sut)
            elif self.sut is not None:
                s_dict[type(self.sut)] = self.sut
            if hasattr(self.sm, "singletons") and isinstance(self.sm.singletons, dict):
                s_dict.update(self.sm.singletons)
            try:
                from support.lib.lifecycle import get_active_scope

                scope = get_active_scope()
                instances_by_desc = getattr(scope, "_instances_by_desc", None)
                if instances_by_desc is not None and isinstance(
                    instances_by_desc, dict
                ):
                    for inst in instances_by_desc.values():
                        if inst not in s_dict.values():
                            s_dict[type(inst)] = inst
            except Exception:
                pass

            collab_obj = None
            if hasattr(ct, "target") and ct.target is not None:
                from .pretense import _resolve_target_singleton

                collab_obj = _resolve_target_singleton(s_dict, ct.target)
            if collab_obj is None:
                for inst in s_dict.values():
                    if hasattr(inst, ct.name):
                        collab_obj = inst
                        break
            if collab_obj is None:
                try:
                    from support.lib.lifecycle import get_singleton

                    if isinstance(c_spec, type):
                        collab_obj = get_singleton(c_spec)
                except Exception:
                    pass

            collab_state = (
                getattr(collab_obj, "state", None)
                or getattr(collab_obj, "_state", None)
                or getattr(c_proto, "state", None)
            )
            collab_sm = getattr(collab_obj, "_sm", None) or c_proto

            if collab_state is not None and not all(
                req(collab_state, collab_sm) for req in ct.requirements
            ):
                return None

            if call_args or call_kwargs:
                if ct.args_fn is not None:
                    args = ct.args_fn(
                        collab_state, collab_sm, *call_args, **call_kwargs
                    )
                else:
                    args = call_args or tuple(call_kwargs.values())
            else:
                with with_draw(data.draw):
                    if ct.args_fn is not None:
                        import inspect

                        sig = inspect.signature(ct.args_fn)
                        extra_params = [
                            p
                            for p in list(sig.parameters.values())[2:]
                            if p.kind
                            in (
                                inspect.Parameter.POSITIONAL_ONLY,
                                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                            )
                        ]
                        nb_args = [NotBound] * len(extra_params)
                        try:
                            args = ct.args_fn(collab_state, collab_sm, *nb_args)
                        except UnsatisfiedAntecedentError:
                            return None
                    else:
                        args = ()

            if args is None:
                return None

            global _ACTIVE_STEP, _ACTIVE_TRACE
            current_step = TraceStep(
                ct.name, getattr(ct.target, "__name__", None), True, args, {}, None
            )
            self.trace.append(current_step)
            type(self)._last_trace = list(self.trace)
            _ACTIVE_STEP = current_step
            _ACTIVE_TRACE = list(self.trace)

            token_suts = _ACTIVE_SUTS.set(dict(s_dict))
            token_sut = _current_sut.set(collab_obj)
            token_ver = _is_verification.set(
                not getattr(collab_obj, "__is_pretense_fake__", False)
            )
            token_tgt = _current_target.set(collab_obj)
            token_mth = _current_method.set(ct.name)
            token_arg = _current_args.set(args)
            token_kw = _current_kwargs.set({})
            token_sm = _current_sm.set(collab_sm)
            token_exc_type = _last_contracted_exception_type.set(None)

            try:
                res = None
                if collab_obj is not None and hasattr(collab_obj, ct.name):
                    res = getattr(collab_obj, ct.name)(*args)
                elif getattr(ct, "_target_fn", None) is not None:
                    res = ct._target_fn(collab_sm, *args)
                else:
                    if ct.return_fn is not None:
                        res = ct.return_fn(collab_state, collab_sm, *args)
                    if ct.provider is not None:
                        ct.provider(collab_state, collab_sm, *args, result=res)
                current_step = TraceStep(
                    ct.name, getattr(ct.target, "__name__", None), True, args, {}, res
                )
                self.trace[-1] = current_step
            finally:
                _ACTIVE_STEP = None
                _last_contracted_exception_type.reset(token_exc_type)
                _current_sm.reset(token_sm)
                _current_kwargs.reset(token_kw)
                _current_args.reset(token_arg)
                _current_method.reset(token_mth)
                _current_target.reset(token_tgt)
                _is_verification.reset(token_ver)
                _current_sut.reset(token_sut)
                _ACTIVE_SUTS.reset(token_suts)

        collab_rule_method.__name__ = (
            f"step_collab_{c_proto.__class__.__name__}_{ct.name}"
        )
        return collab_rule_method

    attrs: Dict[str, Any] = {}

    def __init__(self: Any) -> None:
        RuleBasedStateMachine.__init__(self)

        if callable(initial_state_factory):
            init_st = initial_state_factory()
        else:
            init_st = initial_state_factory

        if hasattr(proto_inst, "make_state_machine"):
            if init_st is not None:
                self.sm = proto_inst.make_state_machine(init_st)
            else:
                curr_st = getattr(proto_inst, "state", None)
                fresh_st = copy.deepcopy(curr_st) if curr_st is not None else None
                self.sm = proto_inst.make_state_machine(fresh_st)
        elif isinstance(proto, type):
            self.sm = proto(state=init_st) if init_st is not None else proto()
        else:
            self.sm = copy.copy(proto_inst)
            if hasattr(self.sm, "singletons") and isinstance(self.sm.singletons, dict):
                self.sm.singletons = dict(proto_inst.singletons)

        if callable(sut_factory):
            try:
                from support.lib.lifecycle import get_default_registry
                import types as _types

                reg = get_default_registry()
                g = getattr(sut_factory, "__globals__", None)
                if isinstance(g, dict):
                    seen_mods: Set[str] = set()
                    for val in list(g.values()):
                        mod = None
                        if isinstance(val, _types.ModuleType):
                            mod = val
                        elif isinstance(val, type):
                            mod_name = getattr(val, "__module__", "")
                            if mod_name:
                                mod = sys.modules.get(mod_name)
                        if mod is not None:
                            mname = getattr(mod, "__name__", "")
                            leaf = mname.rsplit(".", 1)[-1]
                            if (leaf.endswith("_impl") or leaf.endswith("_asm")) and mname not in seen_mods:
                                seen_mods.add(mname)
                                reg.register_module(mod)
            except Exception:
                pass

        if callable(sut_factory) and isinstance(sut_factory, type):
            if getattr(sut_factory, "__is_pretense_fake__", False):
                self.sut = sut_factory(state=self.sm.state)
            else:
                self.sut = sut_factory()
        elif callable(sut_factory):
            self.sut = sut_factory()
        elif sut_factory is not None:
            self.sut = sut_factory
        elif hasattr(proto_inst, "singletons") and proto_inst.singletons:
            non_fakes = {
                k: v
                for k, v in proto_inst.singletons.items()
                if not getattr(v, "__is_pretense_fake__", False)
            }
            if non_fakes:
                self.sut = dict(non_fakes)
            else:
                fake_cls = pretense.synthesize_fake(
                    proto if isinstance(proto, type) else type(proto)
                )
                self.sut = fake_cls(state=self.sm.state)
        else:
            fake_cls = pretense.synthesize_fake(
                proto if isinstance(proto, type) else type(proto)
            )
            self.sut = fake_cls(state=self.sm.state)

        if getattr(self.sut, "__is_pretense_fake__", False):
            setattr(self.sut, "_sm", self.sm)
            setattr(self.sut, "_state", self.sm.state)

        if hasattr(self.sm, "bind") and self.sut is not None:
            self.driver = self.sm.bind(self.sut)

        if not hasattr(self.sm, "singletons") or not isinstance(self.sm.singletons, dict):
            self.sm.singletons = {}

        if isinstance(self.sut, dict):
            for k, v in self.sut.items():
                if isinstance(k, type):
                    self.sm.singletons[k] = v
        elif self.sut is not None:
            self.sm.singletons[type(self.sut)] = self.sut
        if collab_list:
            for c_spec in collab_list:
                c_cls = c_spec if isinstance(c_spec, type) else type(c_spec)
                has_collab = False
                for k, inst in self.sm.singletons.items():
                    if isinstance(k, type) and (
                        issubclass(k, c_cls) or issubclass(c_cls, k)
                    ):
                        has_collab = True
                        break
                    if getattr(inst, "__is_pretense_fake__", False):
                        sm_obj = getattr(inst, "_sm", None)
                        if sm_obj is not None and (
                            isinstance(sm_obj, c_cls)
                            or type(sm_obj).__name__ == c_cls.__name__
                        ):
                            has_collab = True
                            break
                if not has_collab:
                    try:
                        fake_collab_cls = pretense.synthesize_fake(c_cls)
                        fake_inst = fake_collab_cls()
                        self.sm.singletons[c_cls] = fake_inst
                        if hasattr(c_cls, "target_protocol"):
                            self.sm.singletons[
                                getattr(c_cls, "target_protocol")
                            ] = fake_inst
                        if hasattr(fake_inst, "_sm") and hasattr(fake_inst._sm, "transitions"):
                            for tr in fake_inst._sm.transitions:
                                if hasattr(tr, "target") and tr.target is not None:
                                    target_cls = getattr(tr.target, "__self__", None)
                                    if isinstance(target_cls, type):
                                        self.sm.singletons[target_cls] = fake_inst
                    except Exception:
                        pass
        self.trace = []

    def teardown(self: Any) -> None:
        if hasattr(self.sut, "teardown"):
            self.sut.teardown()
        elif hasattr(self.sut, "close"):
            self.sut.close()
        elif isinstance(self.sut, dict) and "scope" in self.sut:
            try:
                self.sut["scope"].__exit__(None, None, None)
            except (AttributeError, RuntimeError, OSError):
                pass

    attrs["__init__"] = __init__
    attrs["teardown"] = teardown
    attrs["__test__"] = False

    transitions = getattr(proto_inst, "transitions", [])
    for t in transitions:
        attrs[f"step_{t.name}"] = make_rule_method(t)

    for c_spec in collab_list:
        c_proto = c_spec() if isinstance(c_spec, type) else c_spec
        for ct in getattr(c_proto, "transitions", []):
            if getattr(ct, "is_seeding", False):
                attrs[f"step_collab_{c_proto.__class__.__name__}_{ct.name}"] = (
                    make_collab_rule_method(c_spec, ct)
                )

    cls: Type[RuleBasedStateMachine] = type(class_name, (RuleBasedStateMachine,), attrs)
    if settings is not None:
        cls.TestCase.settings = settings
    return cls


pretense.StateMachine.register_compiler(compile_hypothesis_test_case)


# ============================================================================
# Runner and CLI
# ============================================================================


def _configure_sys_path(paths: Optional[List[Path]] = None) -> None:
    """Configures sys.path by resolving cwd, target parts roots, and pythonpath in pyproject.toml."""
    cwd = Path.cwd().resolve()
    if str(cwd) not in sys.path:
        sys.path.insert(0, str(cwd))

    if paths:
        for p in paths:
            curr = p.resolve()
            for parent in [curr, *curr.parents]:
                if parent.name == "parts":
                    parent_str = str(parent)
                    if parent_str not in sys.path:
                        sys.path.insert(0, parent_str)
                    _add_parts_lib_paths(parent.parent)
                    break

    pyproject = cwd / "pyproject.toml"
    if pyproject.is_file():
        try:
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
        except (ValueError, OSError, tomllib.TOMLDecodeError):
            pass

    # Auto-discover parts/*/lib/ and parts/*/low/ for dynamic module imports
    _add_parts_lib_paths(cwd)


def _add_parts_lib_paths(root: Path) -> None:
    """Add lib/ and low/ directories from parts/*/ to sys.path."""
    parts_dir = root / "parts"
    if not parts_dir.is_dir():
        return
    for entry in sorted(parts_dir.iterdir()):
        if entry.is_dir():
            for role in ("lib", "low", "pretense"):
                role_dir = entry / role
                if role_dir.is_dir():
                    rp = str(role_dir.resolve())
                    if rp not in sys.path:
                        sys.path.append(rp)


class _PretenseTestTarget:
    """Represents a discovered test target (compiled RuleBasedStateMachine or Proto)."""

    def __init__(
        self,
        name: str,
        file_path: Path,
        test_case_cls: Any,
        proto: Optional[Any] = None,
    ) -> None:
        self.name = name
        self.file_path = file_path
        self.test_case_cls = test_case_cls
        self.proto = proto


def discover_targets(
    paths: List[Path],
    keyword: Optional[str] = None,
    no_fuzz: bool = False,
    loading_errors: Optional[List[Tuple[Path, str]]] = None,
) -> List[_PretenseTestTarget]:
    """Discover state machine test targets across the specified paths."""
    _configure_sys_path(paths)
    discovered_files: List[Path] = []

    for path in paths:
        if path.is_file() and path.suffix == ".py":
            discovered_files.append(path.resolve())
        elif path.is_dir():
            for root, _, files in os.walk(path):
                root_path = Path(root)
                if root_path.name == "pretense" or any(
                    f.endswith("_pretense.py") for f in files
                ):
                    for f in files:
                        if (
                            f.endswith(".py")
                            and not f.startswith("__")
                            and (
                                root_path.name == "pretense"
                                or f.endswith("_pretense.py")
                            )
                        ):
                            discovered_files.append((root_path / f).resolve())

    unique_files: List[Path] = []
    seen = set()
    for f in discovered_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    targets: List[_PretenseTestTarget] = []

    for file_path in unique_files:
        parent_str = str(file_path.parent.resolve())
        if parent_str not in sys.path:
            sys.path.insert(0, parent_str)
        module_name = f"pretense_dynamic_{file_path.stem}_{abs(hash(str(file_path)))}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            err_msg = f"Cannot create module spec for {file_path}"
            if loading_errors is not None:
                loading_errors.append((file_path, err_msg))
            else:
                raise PretenseSpecificationError(err_msg)
            continue

        try:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)
        except Exception as e:
            tb = traceback.format_exc()
            if loading_errors is not None:
                loading_errors.append((file_path, tb))
            else:
                raise PretenseSpecificationError(
                    f"Failed to load {file_path}: {e}"
                ) from e
            continue

        for attr_name in dir(mod):
            if keyword and keyword.lower() not in attr_name.lower():
                continue

            attr = getattr(mod, attr_name)

            is_fuzz_target = (
                (
                    isinstance(attr, type)
                    and issubclass(attr, RuleBasedStateMachine)
                    and attr is not RuleBasedStateMachine
                )
                or (
                    isinstance(attr, type)
                    and issubclass(attr, unittest.TestCase)
                    and ("Fuzz" in attr_name or "fuzz" in attr_name.lower())
                )
                or isinstance(attr, StateMachineProto)
                or hasattr(attr, "transitions")
            )
            if no_fuzz and is_fuzz_target:
                continue

            if (
                isinstance(attr, type)
                and issubclass(attr, RuleBasedStateMachine)
                and attr is not RuleBasedStateMachine
            ):
                targets.append(
                    _PretenseTestTarget(
                        name=attr_name, file_path=file_path, test_case_cls=attr.TestCase
                    )
                )
            elif isinstance(attr, type) and issubclass(attr, unittest.TestCase):
                targets.append(
                    _PretenseTestTarget(
                        name=attr_name, file_path=file_path, test_case_cls=attr
                    )
                )
            elif (
                isinstance(attr, type)
                and attr_name.endswith("Test")
                and hasattr(attr, "run_all")
            ):
                targets.append(
                    _PretenseTestTarget(
                        name=attr_name, file_path=file_path, test_case_cls=attr
                    )
                )
            elif isinstance(attr, StateMachineProto) or hasattr(attr, "transitions"):
                sut_factory = getattr(mod, "get_sut", None) or getattr(
                    mod, "create_sut", None
                )
                state_factory = getattr(mod, "get_initial_state", None) or getattr(
                    mod, "initial_state", None
                )
                if callable(sut_factory) and callable(state_factory):
                    compiled = compile_hypothesis_test_case(
                        proto=attr,
                        sut_factory=sut_factory,
                        initial_state_factory=state_factory,
                        name=f"Compiled_{attr_name}",
                    )
                    targets.append(
                        _PretenseTestTarget(
                            name=attr_name,
                            file_path=file_path,
                            test_case_cls=compiled.TestCase,
                            proto=attr,
                        )
                    )

    return targets


def _prioritize_exception_group_trace(tb: str) -> str:
    """Prioritizes the shortest sub-exception trace in an ExceptionGroup to isolate minimal reproduction, deduplicating equivalent failures."""
    m = re.search(r"ExceptionGroup:\s*Hypothesis found (\d+) distinct failures", tb)
    if not m:
        return tb
    total_failures = int(m.group(1))

    parts = re.split(r"(?:\n\s*(?:\+-\+|\+)\s*-+\s*\d+\s*-+)", tb)
    if len(parts) <= 2:
        return tb

    header = parts[0].strip()
    sub_blocks = [b.strip() for b in parts[1:]]

    # Cluster sub-exceptions by terminal failure signature: (exception_type, last_frame_file, last_frame_func)
    # Equivalent failure paths ending at the same location are treated as duplicates; keep shortest trace per cluster.
    clusters: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for idx, block in enumerate(sub_blocks, 1):
        lines = [l.strip().lstrip("|").strip() for l in block.splitlines() if l.strip()]
        exc_lines = [
            l
            for l in lines
            if ("Error:" in l or "AssertionError" in l)
            and not l.startswith("Draw")
            and not l.startswith("state.")
        ]
        last_exc = exc_lines[-1] if exc_lines else "UnknownError"
        exc_type = last_exc.split(":")[0].split(".")[-1]

        frames = re.findall(r"File \"([^\"]+)\", line (\d+), in (\w+)", block)
        if frames:
            last_file = frames[-1][0].split("/")[-1]
            last_func = frames[-1][2]
        else:
            last_file = "unknown"
            last_func = "unknown"

        sig = (exc_type, last_file, last_func)
        line_count = len(block.splitlines())
        if sig not in clusters or line_count < clusters[sig]["line_count"]:
            clusters[sig] = {
                "idx": idx,
                "block": block,
                "line_count": line_count,
                "sig": sig,
            }

    unique_failures = sorted(clusters.values(), key=lambda x: x["line_count"])
    primary = unique_failures[0]
    p_idx = primary["idx"]
    p_sig = primary["sig"]
    p_lines = primary["line_count"]

    indent_block = "\n".join(
        "    " + line if line else "" for line in primary["block"].splitlines()
    )
    res = [
        header,
        f"\n[Hypothesis found {total_failures} failures across {len(unique_failures)} unique defect signatures. Prioritizing shortest unique failure ({p_idx}/{total_failures}); {total_failures - 1} redundant or longer traces omitted]:",
        f"  +-+---------------- Shortest Trace: {p_sig[0]} in {p_sig[1]}:{p_sig[2]} ({p_lines} lines) ----------------\n{indent_block}",
    ]
    if len(unique_failures) > 1:
        res.append(
            "\nOther unique defect signatures identified (will be tested in subsequent runs):"
        )
        for u in unique_failures[1:4]:
            u_sig = u["sig"]
            u_lines = u["line_count"]
            res.append(f"  • {u_sig[0]} in {u_sig[1]}:{u_sig[2]} ({u_lines} lines)")
        if len(unique_failures) > 4:
            res.append(
                f"  • ... and {len(unique_failures) - 4} other unique defect signatures."
            )

    return "\n".join(res)


def format_prioritized_failure_details(errors: List[Tuple[Any, str]]) -> str:
    """Formats test failure details prioritizing the shortest stack trace across failures and exception groups."""
    if not errors:
        return "Test failed."

    # Sort errors by traceback length ascending so the shortest trace appears first
    sorted_errors = sorted(errors, key=lambda item: len(item[1].splitlines()))

    formatted_blocks: List[str] = []
    for test_case, tb in sorted_errors:
        prioritized_tb = _prioritize_exception_group_trace(tb.strip())
        formatted_blocks.append(f"=== {test_case} ===\n{prioritized_tb}")

    return "\n\n".join(formatted_blocks)


def run_pretense_cli(argv: Optional[List[str]] = None) -> int:
    """CLI test execution entry point (uv run pretense ...)."""
    parser = argparse.ArgumentParser(
        prog="pretense",
        description="Pretense: Declarative State-Machine Testing & Verification Engine",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to discover test suites in.",
    )
    parser.add_argument(
        "-k", "--keyword", default=None, help="Filter tests by name expression."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose test execution output."
    )
    parser.add_argument(
        "-s",
        "--synthesize",
        action="store_true",
        help="Synthesize standalone unit test on failure.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run fast smoke test with minimal fuzz iterations (3 examples).",
    )
    parser.add_argument(
        "--no-fuzz",
        action="store_true",
        help="Disable random property fuzzing (1 scenario iteration).",
    )
    parser.add_argument(
        "--cov", action="store_true", help="Run with coverage tracking."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=100.0,
        help="Required minimum coverage threshold percentage.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout in seconds per target (default: 45.0, or $PRETENSE_TIMEOUT). Set to 0 to disable.",
    )

    args = parser.parse_args(argv)

    raw_timeout = args.timeout
    if raw_timeout is None:
        raw_timeout = WatchdogMonitor.resolve_timeout(default=45.0)
    timeout_seconds = max(0.0, raw_timeout)

    def _collect_lib_impls_from_dir(lib_dir: Path) -> Set[str]:
        res: Set[str] = set()
        py_files = [
            f
            for f in lib_dir.glob("*.py")
            if not f.name.startswith("__") and f.is_file()
        ]
        stems = {f.stem for f in py_files}
        for f in py_files:
            # If this is <name>.py and <name>_impl.py also exists in the same lib dir,
            # <name>.py is an abstract interface stub; exclude it from implementation coverage.
            if f"{f.stem}_impl" in stems:
                continue
            res.add(str(f.resolve()))
        return res

    def _is_interface_pretense_file(test_file: Path) -> bool:
        if not (test_file.is_file() and test_file.parent.name == "pretense"):
            return False
        stem = test_file.stem
        unit_name = stem[:-9] if stem.endswith("_pretense") else stem
        if unit_name.endswith("_impl"):
            return False
        part_dir = test_file.parent.parent
        if (
            (part_dir / "lib" / f"{unit_name}_impl.py").is_file()
            or (part_dir / "low" / f"{unit_name}_impl.pyi").is_file()
            or (part_dir / "high" / f"{unit_name}_impl.md").is_file()
        ):
            return True
        try:
            src = test_file.read_text(encoding="utf-8")
            return "LifecycleTestCase" not in src and "as_checked" not in src
        except OSError:
            return False

    def _resolve_target_lib_for_test_file(test_file: Path) -> Set[str]:
        if _is_interface_pretense_file(test_file):
            return {str(test_file.resolve())}
        res: Set[str] = set()
        if (
            test_file.is_file()
            and test_file.parent.name == "pretense"
            and (test_file.parent.parent / "lib").is_dir()
        ):
            lib_dir = test_file.parent.parent / "lib"
            stem = test_file.stem
            unit_name = stem[:-9] if stem.endswith("_pretense") else stem
            candidate = lib_dir / f"{unit_name}.py"
            if candidate.is_file():
                if not (lib_dir / f"{unit_name}_impl.py").is_file():
                    res.add(str(candidate.resolve()))
            else:
                res.update(_collect_lib_impls_from_dir(lib_dir))
        return res

    target_paths = [Path(p) for p in args.paths]
    target_lib_files: Set[str] = set()
    has_non_interface_target = False
    for p in target_paths:
        p_res = p.resolve()
        if p_res.is_file():
            if not _is_interface_pretense_file(p_res):
                has_non_interface_target = True
            target_lib_files.update(_resolve_target_lib_for_test_file(p_res))
        elif p_res.is_dir():
            has_non_interface_target = True
            if p_res.name == "pretense" and (p_res.parent / "lib").is_dir():
                for t_file in p_res.glob("*_pretense.py"):
                    target_lib_files.update(_resolve_target_lib_for_test_file(t_file))
                if not target_lib_files:
                    target_lib_files.update(
                        _collect_lib_impls_from_dir(p_res.parent / "lib")
                    )
            for root, _, files in os.walk(p_res):
                r_path = Path(root)
                if r_path.name == "pretense" and (r_path.parent / "lib").is_dir():
                    for f in files:
                        if f.endswith("_pretense.py"):
                            target_lib_files.update(
                                _resolve_target_lib_for_test_file(r_path / f)
                            )
                    if not target_lib_files:
                        target_lib_files.update(
                            _collect_lib_impls_from_dir(r_path.parent / "lib")
                        )
                elif r_path.name == "lib" and "support" not in r_path.parts:
                    target_lib_files.update(_collect_lib_impls_from_dir(r_path))

    cov_engine = None
    if args.cov:
        cov_mod = importlib.import_module("coverage")
        cov_engine = cov_mod.Coverage(branch=False)
        cov_engine.start()

    effective_no_fuzz = args.no_fuzz or (args.cov and has_non_interface_target)
    loading_errors: List[Tuple[Path, str]] = []
    targets = discover_targets(
        target_paths,
        keyword=args.keyword,
        no_fuzz=effective_no_fuzz,
        loading_errors=loading_errors,
    )
    if loading_errors:
        sys.stderr.write(
            f"\n[FAIL] Pretense failed to load {len(loading_errors)} test module(s):\n"
        )
        for fpath, tb in loading_errors:
            sys.stderr.write(f"\n--- Loading Error: {fpath} ---\n{tb}\n")
        return 1

    if not targets:
        sys.stderr.write(
            f"Error: No Pretense test targets found in: {', '.join(str(p) for p in target_paths)}\n"
        )
        return 1

    print(f"=== Running Pretense State Machine Suites ({len(targets)} targets) ===")
    if timeout_seconds > 0:
        print(f"Per-target watchdog timeout: {timeout_seconds:.1f}s")

    total_passed = 0
    total_failed = 0
    suite_start = time.time()

    for idx, target in enumerate(targets, 1):
        target_name = f"{target.file_path.name}::{target.name}"
        sys.stdout.write(f"[{idx}/{len(targets)}] {target_name} ... ")
        sys.stdout.flush()

        watchdog_handle = WatchdogMonitor.arm(timeout_seconds, target_name=target_name)
        start_time = time.time()
        success = False
        error_msg = None

        try:
            if args.smoke:
                if hasattr(target.test_case_cls, "settings"):
                    from hypothesis import settings as hyp_settings, HealthCheck

                    target.test_case_cls.settings = hyp_settings(
                        max_examples=3,
                        stateful_step_count=5,
                        deadline=None,
                        suppress_health_check=[
                            HealthCheck.too_slow,
                            HealthCheck.filter_too_much,
                        ],
                    )
            if hasattr(target.test_case_cls, "run_all") and callable(
                target.test_case_cls.run_all
            ):
                runner_inst = target.test_case_cls()
                runner_inst.run_all()
                success = True
            else:
                suite = unittest.TestSuite()
                loader = unittest.TestLoader()
                suite.addTest(loader.loadTestsFromTestCase(target.test_case_cls))
                result = unittest.TestResult()
                suite.run(result)

                if result.wasSuccessful():
                    success = True
                else:
                    success = False
                    errors = result.failures + result.errors
                    if errors:
                        error_msg = format_prioritized_failure_details(errors)
                    else:
                        error_msg = "Test failed."
        except (
            AssertionError,
            PretenseSpecificationError,
            RuntimeError,
            ValueError,
            TypeError,
        ) as e:
            success = False
            error_msg = _prioritize_exception_group_trace(traceback.format_exc())
        finally:
            WatchdogMonitor.disarm(watchdog_handle)

        elapsed = time.time() - start_time
        if success:
            total_passed += 1
            print(f"PASSED ({elapsed:.2f}s)")
        else:
            total_failed += 1
            print(f"FAILED ({elapsed:.2f}s)")
            if error_msg:
                print(f"\n--- Failure Details: {target_name} ---\n{error_msg}")
                if "Failing test case:" in error_msg:
                    failing_lines = []
                    capture = False
                    for line in error_msg.splitlines():
                        if "Failing test case:" in line:
                            capture = True
                            continue
                        if capture:
                            if line.strip().startswith(("+", "===", "---")) or (
                                "Traceback" in line and not line.strip().startswith("|")
                            ):
                                break
                            clean_line = line.strip().lstrip("|").strip()
                            if clean_line and not clean_line.startswith("Explanation:"):
                                failing_lines.append(clean_line)
                    if failing_lines:
                        print("\n=== Synthesized Deterministic Regression Scenario ===")
                        print(
                            "# Minimal counterexample sequence extracted from Hypothesis:"
                        )
                        for fl in failing_lines:
                            print(f"#   {fl}")
                        print("======================================================")
            diag = format_active_step_diagnostic(
                "Active Step Diagnostic at failure", target_name=target_name
            )
            if diag:
                print(f"\n{diag}")

    total_time = time.time() - suite_start
    print(
        f"\nSummary: {total_passed} passed, {total_failed} failed in {total_time:.2f}s"
    )
    if total_failed > 0:
        print(
            "\n" + "=" * 80 + "\n"
            "[QA ARBITER REMINDER - EXPLAIN DEFECTS IN TERMS OF SPECIFICATION]\n"
            "• Blame feedback MUST be provided in terms of how the file being blamed is not compliant with the common source of truth specification.\n"
            "• Line numbers MAY be mentioned ONLY IF they reference the file being blamed.\n"
            "• DO NOT expose details (line numbers, code snippets, or internal symbols) of other files.\n"
            "• Frame test failures strictly as contract discrepancies against the specification.\n"
            "• Explain the expected postcondition outcome versus the observed behavior.\n"
            "• Checked preconditions raising contracted errors (*Error) MUST be tested in scenario tests via self.checked.violating(ExpectedError).<method>(...). However, tests must never assert graceful returns on precondition violations, and cannot execute transitions after violating(...) because system state after an error is undefined and violating(...) is strictly terminal. Preconditions without errors define undefined behavior and are untestable.\n"
            + "="
            * 80
        )

    if cov_engine is not None:
        cov_engine.stop()
        cov_engine.save()
        measured = set(cov_engine.get_data().measured_files())
        morfs: Optional[List[str]] = None
        if target_lib_files:
            matched = [
                f for f in measured if str(Path(f).resolve()) in target_lib_files
            ]
            if matched:
                morfs = matched
        if morfs is None:
            morfs = [
                f
                for f in measured
                if "/lib/" in f
                and "/support/" not in f
                and "/pretense/" not in f
                and not Path(f).name.startswith("__")
            ]
        total_cov = cov_engine.report(morfs=morfs if morfs else None, show_missing=True)
        if total_cov < args.threshold:
            print(
                f"\n[FAIL] Coverage threshold not met: {total_cov:.1f}% < {args.threshold:.1f}%"
            )
            print(
                "\n" + "=" * 80 + "\n"
                "[COVERAGE ARBITER REMINDER - EXPLAIN FEEDBACK IN TERMS OF SPECIFICATION]\n"
                "• Blame feedback MUST be provided in terms of how the file being blamed is not compliant with the common source of truth specification.\n"
                "• Line numbers MAY be mentioned ONLY IF they reference the file being blamed.\n"
                "• DO NOT expose details (line numbers, code snippets, or internal symbols) of other files.\n"
                "• Translate uncovered statements and branches into missing specification requirements or scenario cases.\n"
                "• If an uncovered branch is an unreachable defensive check or caller assumption guaranteed by the specification, instruct the implementation author to prune it or mark it as unreachable according to the methodology.\n"
                "• If an uncovered line persists after tests were updated or across multiple rounds, examine the library implementation closely: trace control flow and invariants to verify whether the line is structurally unreachable or defensive dead code; if unreachable, blame the library (prune, with unreachable:, or unreachable()).\n"
                + "="
                * 80
            )
            return 1

    return 0 if (total_failed == 0 and total_passed > 0) else 1


def main(argv: Optional[List[str]] = None) -> int:
    return run_pretense_cli(argv)


# ============================================================================
# Engine Singleton Implementation
# ============================================================================


class PretenseEngine(pretense.PretenseEngine):
    """Realizes state machine compilation, test suite execution, watchdog timeouts, and fake synthesis."""

    def compile_state_machine(self, machine_cls: Type[Any]) -> Type[Any]:
        sut_factory = (
            getattr(machine_cls, "get_sut", None)
            or getattr(machine_cls, "create_sut", None)
            or (lambda: None)
        )
        state_factory = (
            getattr(machine_cls, "get_initial_state", None)
            or getattr(machine_cls, "initial_state", None)
            or (lambda: None)
        )
        proto = (
            machine_cls()
            if isinstance(machine_cls, type)
            and issubclass(machine_cls, StateMachineProto)
            else pretense.StateMachine()
        )
        return compile_hypothesis_test_case(proto, sut_factory, state_factory)

    def run_suite(self, config: PretenseRunnerConfig) -> PretenseRunResult:
        cmd_args: List[str] = list(config.target_paths)
        if not config.fuzz:
            cmd_args.append("--no-fuzz")
        if config.cov:
            cmd_args.append("--cov")
            cmd_args.extend(["--threshold", str(config.cov_threshold)])
        if config.timeout is not None:
            cmd_args.extend(["--timeout", str(config.timeout)])
        if config.synthesize:
            cmd_args.append("--synthesize")

        exit_code = run_pretense_cli(cmd_args)
        return PretenseRunResult(
            passed=1 if exit_code == 0 else 0,
            failed=0 if exit_code == 0 else 1,
            is_passing=(exit_code == 0),
        )

    def synthesize_test(self, target_cls: Type[Any], trace: Sequence[TraceStep]) -> str:
        proto_name = getattr(target_cls, "__name__", "TargetProto")
        state_name = f"{proto_name}State"
        lines = [
            f"def test_{proto_name.lower()}_counterexample() -> None:",
            '    """Synthesized deterministic regression test minimizing counterexample."""',
            f"    sm = {proto_name}.make_state_machine({state_name}())",
            "",
        ]
        for i, step in enumerate(trace, 1):
            args_repr = ", ".join(repr(a) for a in step.args)
            if step.is_seeding:
                lines.append(f"    # Step {i}: Seeding transition")
                lines.append(f"    sm.{step.transition_name}({args_repr})")
            else:
                lines.append(
                    f"    # Step {i}: Method transition '{step.transition_name}'"
                )
                lines.append(
                    f"    sm.dispatch_transition({step.transition_name!r}, {args_repr})"
                )
            lines.append("")
        lines.append("    # Verify invariants hold at conclusion")
        lines.append("    sm.check_invariants()")
        return "\n".join(lines)

    def synthesize_fake(self, machine_cls: Type[Any]) -> Type[Any]:
        return pretense.synthesize_fake(machine_cls)


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        PretenseEngine,
        keys=[PretenseEngine, pretense.PretenseEngine],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
