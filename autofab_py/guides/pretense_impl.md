# Guide: Pretense Implementation State Machine and Test Author

## Summary

The artifact is a Pretense implementation module (`pretense/<name>_pretense.py`) verifying `lib/<name>.py` against `low/<name>.pyi` and the upstream stateless `<Iface>StateMachine` imported from `pretense`, submitted via `submit(...)`. Tool-managed metadata must not be edited manually. The module defines `<Impl>StateMachine(<Iface>StateMachine)` (stateless, inheriting all `@transition`, `require`, `require_arg`, and `require_env` contracts from `<Iface>StateMachine`), `Test<Impl>Real(LifecycleTestCase)` when fixed scenarios are needed (e.g. for `.violating(...)` or coverage feedback), and `<Impl>FuzzTest = compile_hypothesis_test_case(<Impl>StateMachine, sut_factory=make_sut, name="<Impl>FuzzTest")`.

API signatures: `sut(TargetClass) -> TargetClass` (imported from `pretense` and called inside `inner_*` on `<Impl>StateMachine`); `self.sm.as_checked(Iface, self.sut) -> CheckedAdapter[Iface]` (inside `Test<Impl>Real.setUp`, where `LifecycleTestCase` defines `target = <ImplClass>`); `self.checked.violating(ExpectedError).<method>(...)` for `*Error` contract violations; `with self.assertRaises(ExpectedException):` for `*Exception` operational exceptions; `compile_hypothesis_test_case(sm_cls, *, sut_factory=make_sut, name=...)` where `make_sut() -> TargetClass | dict[type[Any], Any]` registers singletons in a `LifecycleRegistry` and enters `enter_phase(system, registry=registry)`. Environmental `@test_only` guards in `inner_<guard>` delegate to the corresponding `@test_only` methods on imported collaborator singletons (which are synthesized fakes during implementation testing). Accessing `self.checked.<prop>` invokes the `@transition(name="<prop>")` transition and returns the property value.

> META: "Implementation pretense modules inherit the stateless interface contract and supply only the concrete SUT bindings, collaborator fake wiring, and real-SUT fuzz/scenario tests."

## Verification failure

Implementation modules are verified statically in `bin/check_files` (`pretense_lint`, `pyright`) and executed downstream by `pretense_qa` and `pretense_coverage`. When static verification passes on modified code, conclude via `submit(target="<target_file>", change_summary="...")`; when unchanged and ready solely due to pending downstream cleaning ("Target has not been cleaned"), conclude via `bin/submit <target_file>` with no change summary. Invoking `fail` or `reject` after modifying code that passes verification is prohibited. If the target is unmodified and feedback is incorrect, invoke `reject(target="<target_file>", reason="<explanation>")`.

## Lint checks

- [ ] Module defines zero state dataclasses (`PN_IMPL_NO_STATE_CLASS`) and `<Impl>StateMachine` inherits all implemented `<Iface>StateMachine` classes from `pretense` (`PRE_LINT_MULTI_INTERFACE_INHERITANCE`)
- [ ] `<Impl>StateMachine` contains zero `require_arg`, zero `require` (`PN_IMPL_NO_REQUIRE_ARG`), zero `@transition` overrides (`PN_IMPL_NO_OUTER_TRANSITION`), and zero `require_arg`/`Domain`/`transition` imports
- [ ] `inner_<method>` methods in `<Impl>StateMachine` never call `super()` (`PRE_LINT_NO_SUPER_IN_IMPL_INNER`) and never mutate `self.state` (`PN_IMPL_NO_STATE_MUTATION`)
- [ ] `make_sut()` contains zero loops and zero state arguments (`PRE_LINT_NO_PRE_SEEDING`); `Test<Impl>Real` never mutates `.state` directly (`PRE_LINT_NO_STATE_POKING`) and never binds or accesses `self.real` (`PN_NO_DIRECT_REAL_ACCESS`)
- [ ] `.violating(...)` is used only for `*Error` (`PRE_LINT_VIOLATING_MUST_BE_ERROR`), never `*Exception`, and at most once per test method as the terminal statement (`PN_TERMINAL_VIOLATING`)
- [ ] Module defines `<Impl>FuzzTest = compile_hypothesis_test_case(...)` and/or `Test<Impl>Real(LifecycleTestCase)` with non-trivial scenario executions
- [ ] Target imports use package-qualified paths (`from <scope>.parts.<unit>.lib.<module> import ...`); Pyright passes with zero errors and zero type suppressions; read-only Pretense API stubs are available in `support/lib/pretense.pyi`

## Implementation state machine and tests

- [ ] Override `inner_<method>(self, ...)` to resolve `target = sut(TargetClass)` and invoke the concrete method, adding only implementation-specific assertions
- [ ] Delegate `@test_only` environmental guard `inner_<guard>(self)` methods exclusively to public or `@test_only` members on `sut(TargetClass)` / `sut(Collaborator)`
- [ ] Wire collaborator fakes in `make_sut()` (using `make_<collab>_fake` from `pretense`) and register them via `LifecycleRegistry` / `sut_factory`; for multi-protocol units implementing multiple `@singleton_type` protocols, inherit all corresponding `<Iface>StateMachine` classes on `<Impl>StateMachine` and have `make_sut()` return `dict[type[Any], Any]` mapping each protocol (or impl class) to its singleton instance
- [ ] Use `self.checked = self.sm.as_checked(Iface, self.sut)` in `Test<Impl>Real(LifecycleTestCase)` (with `target = <ImplClass>` for single-protocol units, or `target = <impl_module>` for multi-protocol units) and call `self.checked.violating(ExpectedError).<method>(...)` only for contracted `*Error` branches
- [ ] `inner_<method>` overrides and `Test<Impl>Real` test methods use brief plain-prose docstrings or comments describing exercised behavior or failure modes and never cite specification contract slugs (`[slug:...]` or `<unit>.<contract>.<facet>`)
