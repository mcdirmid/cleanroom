"""Unit tests for Cleanroom Specification Toolchain (lint, inherit, link)."""

import ast
import tempfile
import unittest
from pathlib import Path

from update_with_ai.support.lib.grounding_tool import (
    SpecLintVisitor,
    lint_file,
    SpecRegistry,
    compile_module_inheritance,
    DocstringContract,
    ClosedWorldLinker,
    run_pipeline,
    collect_paths,
)


class TestSpecLint(unittest.TestCase):
    """Tests for grounding_tool.py AST static validation."""

    def test_valid_spec(self):
        source = '''
from framework import singleton_type, override, operation
from typing import Optional

@singleton_type("agent_session")
class MyService:
    """
    PURPOSE:
    A valid specification service
    """

    @property
    def name(self) -> str:
        """
        PURPOSE:
        Name of service
        """
        ...

    @operation
    def do_action(self, count: int) -> Optional[str]:
        """
        PURPOSE:
        Execute action

        FRESH_REQUIREMENTS:
        - When count is zero, returns None.
        """
        ...
'''
        tree = ast.parse(source)
        visitor = SpecLintVisitor("<test>")
        visitor.visit(tree)
        self.assertEqual(visitor.diagnostics, [])

    def test_prohibited_statements_rejected(self):
        source = '''
from framework import singleton_type

@singleton_type("agent_session")
class ProhibitedSpec:
    """
    PURPOSE:
    Has illegal statements
    """
    x = 10
    pass
'''
        tree = ast.parse(source)
        visitor = SpecLintVisitor("<test>")
        visitor.visit(tree)
        messages = [d.message for d in visitor.diagnostics]
        self.assertTrue(any("Assign" in m for m in messages))
        self.assertTrue(any("Pass" in m for m in messages))

    def test_empty_data_type_rejected(self):
        source = '''
from framework import data_type

@data_type
class EmptyData:
    """
    PURPOSE:
    Defective empty data type
    """
    ...
'''
        tree = ast.parse(source)
        visitor = SpecLintVisitor("<test>")
        visitor.visit(tree)
        messages = [d.message for d in visitor.diagnostics]
        self.assertTrue(any("Data type 'EmptyData' is empty" in m for m in messages))

    def test_unknown_type_and_typo_rejected(self):
        source = '''
from framework import singleton_type

@singleton_type("agent_session")
class ServiceWithTypo:
    """
    PURPOSE:
    Has typos in types
    """

    @property
    def item(self) -> NonExistentCustomType:
        """
        PURPOSE:
        Typo return type
        """
        ...
'''
        tree = ast.parse(source)
        visitor = SpecLintVisitor("<test>")
        visitor.visit(tree)
        messages = [d.message for d in visitor.diagnostics]
        self.assertTrue(any("Unknown type 'NonExistentCustomType'" in m for m in messages))

    def test_singleton_without_lifecycle_arg_rejected(self):
        source = '''
from framework import singleton_type

@singleton_type
class BareSingleton:
    """
    PURPOSE:
    Missing lifecycle argument
    """
    ...
'''
        tree = ast.parse(source)
        visitor = SpecLintVisitor("<test>")
        visitor.visit(tree)
        messages = [d.message for d in visitor.diagnostics]
        self.assertTrue(any("requires an explicit lifecycle argument" in m for m in messages))

    def test_singleton_invalid_lifecycle_arg_rejected(self):
        source = '''
from framework import singleton_type

@singleton_type("invalid_tier")
class BadTierSingleton:
    """
    PURPOSE:
    Invalid lifecycle argument
    """
    ...
'''
        tree = ast.parse(source)
        visitor = SpecLintVisitor("<test>")
        visitor.visit(tree)
        messages = [d.message for d in visitor.diagnostics]
        self.assertTrue(any("must specify a valid lifecycle tier" in m for m in messages))

    def test_poly_type_with_lifecycle_arg_rejected(self):
        source = '''
from framework import poly_type

@poly_type("system")
class BadPoly:
    """
    PURPOSE:
    Poly types cannot have lifecycle arguments
    """
    ...
'''
        tree = ast.parse(source)
        visitor = SpecLintVisitor("<test>")
        visitor.visit(tree)
        messages = [d.message for d in visitor.diagnostics]
        self.assertTrue(any("does not take lifecycle arguments" in m for m in messages))

    def test_obsolete_base_classes_rejected(self):
        source = '''
from framework import singleton_type

@singleton_type("system")
class BadInheritedSingleton(SystemService):
    """
    PURPOSE:
    Cannot inherit from SystemService
    """
    ...
'''
        tree = ast.parse(source)
        visitor = SpecLintVisitor("<test>")
        visitor.visit(tree)
        messages = [d.message for d in visitor.diagnostics]
        self.assertTrue(any("Direct inheritance from 'SystemService' is obsolete" in m for m in messages))

    def test_inherited_decorator_rejected(self):
        source = '''
from framework import singleton_type, operation

@singleton_type("agent_session")
class GeneratedStub:
    """
    PURPOSE:
    Testing @inherited rejection
    """

    @operation
    @inherited
    def inherited_method(self) -> None:
        """
        PURPOSE:
        Method
        """
        ...
'''
        tree = ast.parse(source)
        v = SpecLintVisitor("<test>")
        v.visit(tree)
        self.assertTrue(any("Unrecognized method decorator '@inherited'" in d.message for d in v.diagnostics))

    def test_operation_decorator_enforced(self):
        source = '''
from framework import singleton_type

@singleton_type("agent_session")
class ServiceWithoutOp:
    """
    PURPOSE:
    Testing operation decorator requirement
    """
    def unannotated_method(self) -> None:
        """
        PURPOSE:
        Method missing @operation
        """
        ...
'''
        tree = ast.parse(source)
        v = SpecLintVisitor("<test>")
        v.visit(tree)
        self.assertTrue(any("must be decorated with either @property or @operation" in d.message for d in v.diagnostics))

    def test_dual_property_and_operation_rejected(self):
        source = '''
from framework import singleton_type, operation

@singleton_type("agent_session")
class ServiceDualDecorator:
    """
    PURPOSE:
    Testing rejection of dual @property and @operation
    """
    @property
    @operation
    def bad_member(self) -> str:
        """
        PURPOSE:
        Conflicting decorators
        """
        ...
'''
        tree = ast.parse(source)
        v = SpecLintVisitor("<test>")
        v.visit(tree)
        self.assertTrue(any("cannot be decorated with both @property and @operation" in d.message for d in v.diagnostics))

    def test_legacy_requirements_header_rejected(self):
        source = '''
from framework import singleton_type, operation

@singleton_type("agent_session")
class ServiceLegacyHeader:
    """
    PURPOSE:
    Testing rejection of legacy REQUIREMENTS:
    """
    @operation
    def run(self) -> None:
        """
        PURPOSE:
        Method
        REQUIREMENTS:
        - Obsolete requirement header
        """
        ...
'''
        tree = ast.parse(source)
        v = SpecLintVisitor("<test>")
        v.visit(tree)
        self.assertTrue(any("Obsolete docstring section 'REQUIREMENTS:'" in d.message for d in v.diagnostics))

    def test_valid_assembly_spec(self):
        source = '''
def __initialize__() -> None:
    """
    PURPOSE:
    Assembles components into test assembly

    CONSTITUENTS:
    - foo_impl
    - bar_impl
    """
    ...
'''
        tree = ast.parse(source)
        v = SpecLintVisitor("test_asm.pyi")
        v.visit(tree)
        self.assertEqual(v.diagnostics, [])

    def test_assembly_spec_in_non_asm_rejected(self):
        source = '''
def __initialize__() -> None:
    """
    PURPOSE:
    Assembles components

    CONSTITUENTS:
    - foo_impl
    """
    ...
'''
        tree = ast.parse(source)
        v = SpecLintVisitor("test.pyi")
        v.visit(tree)
        self.assertTrue(any("only permitted in assembly specifications" in d.message for d in v.diagnostics))

    def test_assembly_spec_missing_constituents_rejected(self):
        source = '''
def __initialize__() -> None:
    """
    PURPOSE:
    Assembles components
    """
    ...
'''
        tree = ast.parse(source)
        v = SpecLintVisitor("test_asm.pyi")
        v.visit(tree)
        self.assertTrue(any("CONSTITUENTS:" in d.message for d in v.diagnostics))


class TestSpecInherit(unittest.TestCase):
    """Tests for grounding_tool.py requirements inheritance engine."""

    def test_docstring_contract_roundtrip(self):
        raw = '''
PURPOSE:
Original service purpose

FRESH_ASSUMPTIONS:
- Must run in POSIX environment

FRESH_REQUIREMENTS:
- Requirement 1
- Requirement 2

INHERITED_REQUIREMENTS:
- [Ancestor] Base requirement
'''
        contract = DocstringContract(raw)
        self.assertEqual(contract.purpose, "Original service purpose")
        self.assertEqual(contract.fresh_assumptions, ["Must run in POSIX environment"])
        self.assertEqual(contract.fresh_requirements, ["Requirement 1", "Requirement 2"])
        self.assertEqual(contract.inherited_requirements, {"Ancestor": ["Base requirement"]})

        rendered = contract.to_docstring()
        self.assertIn("PURPOSE:\nOriginal service purpose", rendered)
        self.assertIn("FRESH_ASSUMPTIONS:\n- Must run in POSIX environment", rendered)
        self.assertIn("FRESH_REQUIREMENTS:\n- Requirement 1\n- Requirement 2", rendered)
        self.assertIn("INHERITED_REQUIREMENTS:\n- [Ancestor] Base requirement", rendered)

        # Test wipe_inherited()
        contract.wipe_inherited()
        self.assertEqual(contract.inherited_requirements, {})
        wiped_rendered = contract.to_docstring()
        self.assertNotIn("INHERITED_REQUIREMENTS:", wiped_rendered)
        self.assertIn("FRESH_REQUIREMENTS:\n- Requirement 1\n- Requirement 2", wiped_rendered)

    def test_inheritance_and_stub_synthesis(self):
        base_src = '''
from framework import poly_type, operation
from typing import Set

@poly_type
class BaseWorker:
    """
    PURPOSE:
    Base worker interface

    FRESH_REQUIREMENTS:
    - Base invariant for workers
    """

    @property
    def worker_id(self) -> str:
        """
        PURPOSE:
        Worker ID
        """
        ...

    @operation
    def execute(self, payload: str) -> bool:
        """
        PURPOSE:
        Execute payload

        FRESH_REQUIREMENTS:
        - Must return True on success.
        """
        ...
'''
        child_src = '''
from framework import singleton_type, override, operation
import base_mod

@singleton_type("agent_session")
class ChildWorker(base_mod.BaseWorker):
    """
    PURPOSE:
    Concrete child worker implementation
    """

    @operation
    @override
    def execute(self, payload: str) -> bool:
        """
        PURPOSE:
        Overridden execution

        FRESH_REQUIREMENTS:
        - Logs execution before returning.
        """
        ...
'''
        registry = SpecRegistry()
        base_tree = ast.parse(base_src)
        child_tree = ast.parse(child_src)

        registry.modules["base_mod"] = base_tree
        registry.module_classes[("base_mod", "BaseWorker")] = base_tree.body[2]
        registry.class_to_modules["BaseWorker"] = {"base_mod"}

        registry.modules["child_mod"] = child_tree
        registry.module_classes[("child_mod", "ChildWorker")] = child_tree.body[2]
        registry.class_to_modules["ChildWorker"] = {"child_mod"}
        registry.imports["child_mod"] = {"base_mod": "base_mod"}

        compiled, diags = compile_module_inheritance(registry, "child_mod")
        self.assertEqual(diags, [])

        # Verify child class inherited BaseWorker class requirements
        self.assertIn("- [BaseWorker] Base invariant for workers", compiled)
        # Verify execute method inherited BaseWorker execute requirements
        self.assertIn("- [BaseWorker] Must return True on success.", compiled)
        # Verify worker_id property was synthesized with @property and @override
        self.assertIn("@property\n    @override\n    def worker_id(self) -> str:", compiled)
        # Verify 'override' and 'operation' were imported from framework
        self.assertIn("override", compiled)
        self.assertNotIn("inherited", compiled)
        self.assertIn("operation", compiled)

    def test_stale_override_without_fresh_contracts_removed(self):
        base_src = '''
from framework import poly_type, operation

@poly_type
class BaseWorker:
    """
    PURPOSE:
    Base worker
    """
    @operation
    def execute(self) -> None:
        """
        PURPOSE:
        Execute action
        """
        ...
'''
        child_src = '''
from framework import singleton_type, override, operation
import base_mod

@singleton_type("agent_session")
class ChildWorker(base_mod.BaseWorker):
    """
    PURPOSE:
    Child worker
    """
    @operation
    @override
    def old_removed_method(self) -> None:
        """
        PURPOSE:
        Stale stub with no fresh contracts
        """
        ...
'''
        registry = SpecRegistry()
        base_tree = ast.parse(base_src)
        child_tree = ast.parse(child_src)
        registry.modules["base_mod"] = base_tree
        registry.module_classes[("base_mod", "BaseWorker")] = base_tree.body[1]
        registry.class_to_modules["BaseWorker"] = {"base_mod"}

        registry.modules["child_mod"] = child_tree
        registry.module_classes[("child_mod", "ChildWorker")] = child_tree.body[2]
        registry.class_to_modules["ChildWorker"] = {"child_mod"}
        registry.imports["child_mod"] = {"base_mod": "base_mod"}

        compiled, diags = compile_module_inheritance(registry, "child_mod")
        self.assertEqual(diags, [])
        # old_removed_method should have been pruned
        self.assertNotIn("old_removed_method", compiled)
        # execute should have been synthesized
        self.assertIn("def execute(self) -> None:", compiled)

    def test_stale_override_with_fresh_contracts_errored(self):
        base_src = '''
from framework import poly_type

@poly_type
class BaseWorker:
    """
    PURPOSE:
    Base worker
    """
    ...
'''
        child_src = '''
from framework import singleton_type, override, operation
import base_mod

@singleton_type("agent_session")
class ChildWorker(base_mod.BaseWorker):
    """
    PURPOSE:
    Child worker
    """
    @operation
    @override
    def specialized_method(self) -> None:
        """
        PURPOSE:
        Method with authored requirements
        FRESH_REQUIREMENTS:
        - Child specific requirement.
        """
        ...
'''
        registry = SpecRegistry()
        base_tree = ast.parse(base_src)
        child_tree = ast.parse(child_src)
        registry.modules["base_mod"] = base_tree
        registry.module_classes[("base_mod", "BaseWorker")] = base_tree.body[1]
        registry.class_to_modules["BaseWorker"] = {"base_mod"}

        registry.modules["child_mod"] = child_tree
        registry.module_classes[("child_mod", "ChildWorker")] = child_tree.body[2]
        registry.class_to_modules["ChildWorker"] = {"child_mod"}
        registry.imports["child_mod"] = {"base_mod": "base_mod"}

        compiled, diags = compile_module_inheritance(registry, "child_mod")
        self.assertTrue(len(diags) > 0)
        self.assertTrue(any("specialized_method" in d.message and "fresh contracts" in d.message for d in diags))

    def test_idempotent_wipe_and_replace(self):
        base_src = '''
from framework import poly_type, operation

@poly_type
class BaseService:
    """
    PURPOSE:
    Base service
    FRESH_REQUIREMENTS:
    - Base invariant
    """
    @operation
    def run(self) -> None:
        """
        PURPOSE:
        Run
        FRESH_REQUIREMENTS:
        - Must complete
        """
        ...
'''
        child_src = '''
from framework import singleton_type
import base_mod

@singleton_type("agent_session")
class ChildService(base_mod.BaseService):
    """
    PURPOSE:
    Child service
    FRESH_REQUIREMENTS:
    - Child invariant
    """
    ...
'''
        registry = SpecRegistry()
        base_tree = ast.parse(base_src)
        child_tree = ast.parse(child_src)

        registry.modules["base_mod"] = base_tree
        registry.module_classes[("base_mod", "BaseService")] = base_tree.body[1]
        registry.class_to_modules["BaseService"] = {"base_mod"}

        registry.modules["child_mod"] = child_tree
        registry.module_classes[("child_mod", "ChildService")] = child_tree.body[2]
        registry.class_to_modules["ChildService"] = {"child_mod"}
        registry.imports["child_mod"] = {"base_mod": "base_mod"}

        # Run 1
        compiled_run1, diags1 = compile_module_inheritance(registry, "child_mod")
        self.assertEqual(diags1, [])

        # Simulate in-place write-back: update registry with compiled_run1
        child_tree_run2 = ast.parse(compiled_run1)
        registry.modules["child_mod"] = child_tree_run2
        registry.module_classes[("child_mod", "ChildService")] = [
            n for n in child_tree_run2.body if isinstance(n, ast.ClassDef) and n.name == "ChildService"
        ][0]

        # Run 2
        compiled_run2, diags2 = compile_module_inheritance(registry, "child_mod")
        self.assertEqual(diags2, [])

        # Verify idempotency
        self.assertEqual(compiled_run1, compiled_run2)


class TestSpecLink(unittest.TestCase):
    """Tests for grounding_tool.py closed-world validation & tier isolation."""

    def test_closed_world_link_pass(self):
        linker = ClosedWorldLinker()
        mod_a = ast.parse('''
from framework import data_type

@data_type
class DataItem:
    """
    PURPOSE:
    Data item
    """
    @property
    def id(self) -> str:
        """
        PURPOSE:
        ID
        """
        ...
''')
        mod_b = ast.parse('''
from framework import singleton_type
from mod_a import DataItem

@singleton_type("agent_session")
class ServiceA:
    """
    PURPOSE:
    Service A
    """
    def get_data(self) -> DataItem:
        """
        PURPOSE:
        Get data
        """
        ...
''')
        linker.modules["mod_a"] = mod_a
        linker.module_paths["mod_a"] = Path("mod_a.pyi")
        linker.module_exports["mod_a"] = {"DataItem"}

        linker.modules["mod_b"] = mod_b
        linker.module_paths["mod_b"] = Path("mod_b.pyi")
        linker.module_exports["mod_b"] = {"ServiceA"}

        linker.check_all()
        self.assertEqual(linker.diagnostics, [])

    def test_missing_symbol_rejected(self):
        linker = ClosedWorldLinker()
        mod_a = ast.parse('''
from framework import data_type

@data_type
class DataItem:
    """
    PURPOSE:
    Data
    """
    @property
    def val(self) -> int:
        """
        PURPOSE:
        Val
        """
        ...
''')
        mod_b = ast.parse('''
from framework import singleton_type
from mod_a import NonExistentItem

@singleton_type("agent_session")
class ServiceB:
    """
    PURPOSE:
    Service B
    """
    ...
''')
        linker.modules["mod_a"] = mod_a
        linker.module_paths["mod_a"] = Path("mod_a.pyi")
        linker.module_exports["mod_a"] = {"DataItem"}

        linker.modules["mod_b"] = mod_b
        linker.module_paths["mod_b"] = Path("mod_b.pyi")
        linker.module_exports["mod_b"] = {"ServiceB"}

        linker.check_all()
        self.assertTrue(any("Symbol 'NonExistentItem' is not exported" in d.message for d in linker.diagnostics))

    def test_tier_isolation_violation_rejected(self):
        linker = ClosedWorldLinker()
        source = '''
from framework import singleton_type

@singleton_type("agent_session")
class SessionWorker:
    """
    PURPOSE:
    Session service
    """
    ...

@singleton_type("system")
class SystemManager:
    """
    PURPOSE:
    System service
    """
    def leak_session(self) -> SessionWorker:
        """
        PURPOSE:
        Illegal cross-tier exposure
        """
        ...
'''
        linker.load_module = lambda p: None  # mock
        tree = ast.parse(source)
        linker.modules["system_mod"] = tree
        linker.module_paths["system_mod"] = Path("system_mod.pyi")
        linker.module_exports["system_mod"] = {"SessionWorker", "SystemManager"}
        linker.class_tiers["SessionWorker"] = "session"
        linker.class_tiers["SystemManager"] = "system"

        linker.check_all()
        self.assertTrue(any("Lifecycle tier violation" in d.message for d in linker.diagnostics))


class TestGroundingToolUnifiedPipeline(unittest.TestCase):
    """Tests for the unified grounding_tool CLI and pipeline execution."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sync_and_check_clean_roundtrip(self):
        parent_spec = self.temp_path / "base_service.pyi"
        parent_spec.write_text('''from framework import poly_type, operation

@poly_type
class BaseService:
    """
    PURPOSE:
    Base contract.

    FRESH_REQUIREMENTS:
    - Base requirement one.
    """

    @operation
    def execute(self, task: str) -> bool:
        """
        PURPOSE:
        Execute task.

        FRESH_REQUIREMENTS:
        - Must complete successfully.
        """
        ...
''')

        child_spec = self.temp_path / "child_service.pyi"
        child_spec.write_text('''from framework import singleton_type
import base_service

@singleton_type("agent_session")
class ChildService(base_service.BaseService):
    """
    PURPOSE:
    Child service.

    FRESH_REQUIREMENTS:
    - Child local requirement.
    """
    ...
''')

        paths = [parent_spec, child_spec]
        # 1. Sync in-place
        exit_code = run_pipeline(paths, mode="sync")
        self.assertEqual(exit_code, 0)

        # Child should now have inlined ancestor requirements and synthesized @override execute stub
        child_content = child_spec.read_text()
        self.assertIn("INHERITED_REQUIREMENTS:", child_content)
        self.assertIn("[BaseService] Base requirement one.", child_content)
        self.assertIn("@override", child_content)
        self.assertNotIn("@inherited", child_content)
        self.assertIn("def execute(self, task: str) -> bool:", child_content)

        # 2. Check should now succeed with zero drift
        exit_code_check = run_pipeline(paths, mode="check")
        self.assertEqual(exit_code_check, 0)

    def test_check_detects_drift_when_unexpanded(self):
        parent_spec = self.temp_path / "parent.pyi"
        parent_spec.write_text('''from framework import poly_type

@poly_type
class Parent:
    """
    PURPOSE:
    Parent.

    FRESH_REQUIREMENTS:
    - Parent requirement.
    """
    ...
''')
        child_spec = self.temp_path / "child.pyi"
        child_spec.write_text('''from framework import singleton_type
import parent

@singleton_type("agent_session")
class Child(parent.Parent):
    """
    PURPOSE:
    Child.
    """
    ...
''')
        # Without sync, child has not inlined parent's requirements
        paths = [parent_spec, child_spec]
        exit_code = run_pipeline(paths, mode="check")
        self.assertEqual(exit_code, 1)

    def test_lint_pass_fails_on_illegal_syntax(self):
        bad_spec = self.temp_path / "bad.pyi"
        bad_spec.write_text('''from framework import singleton_type

@singleton_type("agent_session")
class Bad:
    x = 10
''')
        exit_code = run_pipeline([bad_spec], mode="lint-only")
        self.assertEqual(exit_code, 1)


class TestGroundingArgument(unittest.TestCase):
    """Tests for GROUNDING_ARGUMENT: docstring validation and persistence."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_grounding_argument_in_impl(self):
        impl_spec = self.temp_path / "my_service_impl.pyi"
        impl_spec.write_text('''from framework import singleton_type, operation

@singleton_type("agent_session")
class MyService:
    """
    PURPOSE:
    My service.

    GROUNDING_ARGUMENT:
    Well grounded: this service operates at the session level and has access to session state.
    """

    @operation
    def do_work(self) -> None:
        """
        PURPOSE:
        Do work.

        GROUNDING_ARGUMENT:
        Well grounded: do_work needs no external dependencies.
        """
        ...
''')
        diags = lint_file(str(impl_spec))
        self.assertEqual(diags, [])

    def test_grounding_argument_rejected_in_non_impl(self):
        interface_spec = self.temp_path / "my_service.pyi"
        interface_spec.write_text('''from framework import singleton_type

@singleton_type("agent_session")
class MyService:
    """
    PURPOSE:
    My service.

    GROUNDING_ARGUMENT:
    Should be rejected in non-impl spec.
    """
    ...
''')
        diags = lint_file(str(interface_spec))
        self.assertTrue(any("'GROUNDING_ARGUMENT:' is only permitted in implementation components" in d.message for d in diags))

    def test_grounding_argument_allowed_on_property(self):
        impl_spec = self.temp_path / "prop_impl.pyi"
        impl_spec.write_text('''from framework import singleton_type

@singleton_type("agent_session")
class PropService:
    """
    PURPOSE:
    Service.
    """

    @property
    def value(self) -> int:
        """
        PURPOSE:
        Value property.

        GROUNDING_ARGUMENT:
        Well-grounded: Loaded from external configuration.
        """
        ...
''')
        diags = lint_file(str(impl_spec))
        self.assertEqual(diags, [])

    def test_grounding_argument_rejected_on_property_in_non_singleton(self):
        impl_spec = self.temp_path / "data_impl.pyi"
        impl_spec.write_text('''from framework import data_type

@data_type
class DataRecord:
    """
    PURPOSE:
    Data record.
    """

    @property
    def field(self) -> str:
        """
        PURPOSE:
        Field.

        GROUNDING_ARGUMENT:
        Not allowed on non-singleton types.
        """
        ...
''')
        diags = lint_file(str(impl_spec))
        self.assertTrue(any("'GROUNDING_ARGUMENT:' on members is only permitted on operations or properties of a @singleton_type class." in d.message for d in diags))

    def test_grounding_argument_rejected_on_property_in_non_impl(self):
        interface_spec = self.temp_path / "prop_service.pyi"
        interface_spec.write_text('''from framework import singleton_type

@singleton_type("agent_session")
class PropService:
    """
    PURPOSE:
    Service.
    """

    @property
    def value(self) -> int:
        """
        PURPOSE:
        Value property.

        GROUNDING_ARGUMENT:
        Not allowed in non-impl.
        """
        ...
''')
        diags = lint_file(str(interface_spec))
        self.assertTrue(any("'GROUNDING_ARGUMENT:' is only permitted in implementation components" in d.message for d in diags))

    def test_grounding_argument_preserved_during_sync(self):
        impl_spec = self.temp_path / "sync_service_impl.pyi"
        impl_spec.write_text('''from framework import singleton_type, operation

@singleton_type("agent_session")
class SyncService:
    """
    PURPOSE:
    Service.

    GROUNDING_ARGUMENT:
    Well grounded: class level grounding argument.
    """

    @property
    def status(self) -> str:
        """
        PURPOSE:
        Status property.

        GROUNDING_ARGUMENT:
        Well grounded: property level grounding argument.
        """
        ...

    @operation
    def compute(self) -> None:
        """
        PURPOSE:
        Compute action.

        GROUNDING_ARGUMENT:
        Well grounded: operation level grounding argument.
        """
        ...
''')
        exit_code = run_pipeline([impl_spec], mode="sync")
        self.assertEqual(exit_code, 0)

        content = impl_spec.read_text()
        self.assertIn("GROUNDING_ARGUMENT:\nWell grounded: class level grounding argument.", content)
        self.assertIn("GROUNDING_ARGUMENT:\nWell grounded: property level grounding argument.", content)
        self.assertIn("GROUNDING_ARGUMENT:\nWell grounded: operation level grounding argument.", content)


class TestOrphanRequirements(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_orphan_function(self):
        spec = self.tmp / "sample_ext.pyi"
        spec.write_text('''from framework import data_type

@data_type
class SampleRecord:
    """
    PURPOSE:
    Sample record.
    """
    @property
    def value(self) -> str:
        """
        PURPOSE:
        Value property.
        """
        ...

def __orphan__() -> None:
    """
    PURPOSE:
    Orphaned requirements for sample_ext component.

    FRESH_REQUIREMENTS:
    - Component must maintain ambient environment stability.
    - External network requests must enforce exponential backoff.
    """
    ...
''')
        diags = lint_file(spec)
        self.assertEqual(diags, [])

    def test_orphan_nested_in_class_rejected(self):
        spec = self.tmp / "sample_ext.pyi"
        spec.write_text('''from framework import data_type

@data_type
class SampleRecord:
    """
    PURPOSE:
    Sample record.
    """
    def __orphan__(self) -> None:
        """
        PURPOSE:
        Nested orphan.
        FRESH_REQUIREMENTS:
        - Nested requirement.
        """
        ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("must be a top-level function" in d.message for d in diags))

    def test_orphan_with_arguments_rejected(self):
        spec = self.tmp / "sample_ext.pyi"
        spec.write_text('''from framework import data_type

@data_type
class SampleRecord:
    """
    PURPOSE:
    Sample record.
    """
    @property
    def value(self) -> str:
        """
        PURPOSE:
        Value.
        """
        ...

def __orphan__(arg: int) -> None:
    """
    PURPOSE:
    Orphan with arg.
    FRESH_REQUIREMENTS:
    - Must fail.
    """
    ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("must take no arguments" in d.message for d in diags))

    def test_orphan_with_decorators_rejected(self):
        spec = self.tmp / "sample_ext.pyi"
        spec.write_text('''from framework import data_type, operation

@data_type
class SampleRecord:
    """
    PURPOSE:
    Sample record.
    """
    @property
    def value(self) -> str:
        """
        PURPOSE:
        Value.
        """
        ...

@operation
def __orphan__() -> None:
    """
    PURPOSE:
    Decorated orphan.
    FRESH_REQUIREMENTS:
    - Must fail.
    """
    ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("must not have any decorators" in d.message for d in diags))

    def test_orphan_without_fresh_requirements_rejected(self):
        spec = self.tmp / "sample_ext.pyi"
        spec.write_text('''from framework import data_type

@data_type
class SampleRecord:
    """
    PURPOSE:
    Sample record.
    """
    @property
    def value(self) -> str:
        """
        PURPOSE:
        Value.
        """
        ...

def __orphan__() -> None:
    """
    PURPOSE:
    Orphan missing fresh requirements.
    """
    ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("FRESH_REQUIREMENTS:" in d.message for d in diags))

    def test_orphan_with_disallowed_sections_rejected(self):
        spec = self.tmp / "sample_ext.pyi"
        spec.write_text('''from framework import data_type

@data_type
class SampleRecord:
    """
    PURPOSE:
    Sample record.
    """
    @property
    def value(self) -> str:
        """
        PURPOSE:
        Value.
        """
        ...

def __orphan__() -> None:
    """
    PURPOSE:
    Orphan with grounding argument.

    GROUNDING_ARGUMENT:
    - Well-grounded.

    FRESH_REQUIREMENTS:
    - Something.
    """
    ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("not permitted in '__orphan__'" in d.message for d in diags))

    def test_other_top_level_function_rejected(self):
        spec = self.tmp / "sample_ext.pyi"
        spec.write_text('''from framework import data_type

@data_type
class SampleRecord:
    """
    PURPOSE:
    Sample record.
    """
    @property
    def value(self) -> str:
        """
        PURPOSE:
        Value.
        """
        ...

def other_func() -> None:
    """
    PURPOSE:
    Other function.
    """
    ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("Only imports, class declarations, and '__orphan__' allowed" in d.message for d in diags))

    def test_orphan_preserved_across_sync(self):
        spec = self.tmp / "sample_ext.pyi"
        spec.write_text('''from framework import data_type

@data_type
class SampleRecord:
    """
    PURPOSE:
    Sample record.
    """
    @property
    def value(self) -> str:
        """
        PURPOSE:
        Value.
        """
        ...

def __orphan__() -> None:
    """
    PURPOSE:
    Orphaned requirements.

    FRESH_REQUIREMENTS:
    - External system invariant.
    """
    ...
''')
        exit_code = run_pipeline([spec], mode="sync")
        self.assertEqual(exit_code, 0)

        content = spec.read_text()
        self.assertIn("def __orphan__() -> None:", content)
        self.assertIn("External system invariant.", content)

        # Run check to verify zero drift
        check_code = run_pipeline([spec], mode="check")
        self.assertEqual(check_code, 0)


class TestDataclassProtocolAndExt(unittest.TestCase):
    """Tests for @dataclass(frozen=True), Protocol, and _ext.pyi support."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_dataclass_and_protocol(self):
        spec = self.tmp / "sample_service.pyi"
        spec.write_text('''from dataclasses import dataclass
from typing import Protocol
from framework import data_type, singleton_type, operation

@dataclass(frozen=True)
@data_type
class SampleRecord:
    """
    PURPOSE:
    Sample record.
    """
    def __init__(self, name: str) -> None:
        ...

    @property
    def name(self) -> str:
        """
        PURPOSE:
        Name property.
        """
        ...

@singleton_type("agent_session")
class SampleService(Protocol):
    """
    PURPOSE:
    Sample service protocol.
    """
    @operation
    def run(self, rec: SampleRecord) -> bool:
        """
        PURPOSE:
        Run method.
        """
        ...
''')
        diags = lint_file(spec)
        self.assertEqual(diags, [])

        exit_code = run_pipeline([spec], mode="sync")
        self.assertEqual(exit_code, 0)
        content = spec.read_text()
        self.assertIn("@dataclass(frozen=True)", content)
        self.assertIn("class SampleService(Protocol):", content)

    def test_dataclass_on_singleton_rejected(self):
        spec = self.tmp / "bad_singleton.pyi"
        spec.write_text('''from dataclasses import dataclass
from framework import singleton_type

@dataclass(frozen=True)
@singleton_type("agent_session")
class BadSingleton:
    """
    PURPOSE:
    Bad singleton with dataclass.
    """
    ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("@dataclass can only be applied to @data_type or @variant" in d.message for d in diags))

    def test_valid_external_docstring_spec(self):
        spec = self.tmp / "sample_ext.pyi"
        spec.write_text('''"""
# External Specification: sample_ext

## External Mechanics & API Documentation
Documentation of sample external API.

## Build Dependencies
requirement("sample")

## Usage Snippets
```python
import sample
sample.call()
```
"""
''')
        diags = lint_file(spec)
        self.assertEqual(diags, [])

        exit_code = run_pipeline([spec], mode="sync")
        self.assertEqual(exit_code, 0)

    def test_valid_dataclass_constructor(self):
        spec = self.tmp / "valid_dataclass.pyi"
        spec.write_text('''from dataclasses import dataclass
from framework import data_type
from typing import Optional

@dataclass(frozen=True)
@data_type
class DataItem:
    """
    PURPOSE:
    Data item with constructor.
    """
    def __init__(self, name: str, count: int = ..., tag: Optional[str] = ...) -> None:
        ...

    @property
    def name(self) -> str:
        """
        PURPOSE:
        The name.
        """
        ...
''')
        diags = lint_file(spec)
        self.assertEqual(diags, [])

        exit_code = run_pipeline([spec], mode="sync")
        self.assertEqual(exit_code, 0)
        content = spec.read_text()
        self.assertIn("def __init__(self, name: str, count: int=..., tag: Optional[str]=...) -> None:", content)

    def test_dataclass_constructor_on_service_rejected(self):
        spec = self.tmp / "service_with_init.pyi"
        spec.write_text('''from framework import singleton_type

@singleton_type("agent_session")
class ServiceWithInit:
    """
    PURPOSE:
    Service with init.
    """
    def __init__(self, x: int) -> None:
        ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("Constructor '__init__' is only permitted on @data_type or @variant dataclasses" in d.message for d in diags))

    def test_dataclass_constructor_with_decorator_rejected(self):
        spec = self.tmp / "init_with_dec.pyi"
        spec.write_text('''from dataclasses import dataclass
from framework import data_type, operation

@dataclass(frozen=True)
@data_type
class BadInit:
    """
    PURPOSE:
    Init with operation decorator.
    """
    @operation
    def __init__(self, x: int) -> None:
        ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("Dataclass constructor '__init__' must not have any decorators" in d.message for d in diags))

    def test_dataclass_init_false_without_constructor_allowed(self):
        spec = self.tmp / "init_false_valid.pyi"
        spec.write_text('''from dataclasses import dataclass
from framework import data_type

@dataclass(frozen=True, init=False)
@data_type
class ServiceConstructedPath:
    """
    PURPOSE:
    Service constructed path record.
    """
    @property
    def path(self) -> str:
        """
        PURPOSE:
        Path string.
        """
        ...
''')
        diags = lint_file(spec)
        self.assertEqual(diags, [])

    def test_dataclass_init_false_with_constructor_rejected(self):
        spec = self.tmp / "init_false_invalid.pyi"
        spec.write_text('''from dataclasses import dataclass
from framework import data_type

@dataclass(frozen=True, init=False)
@data_type
class BadInitFalse:
    """
    PURPOSE:
    Bad init false with constructor.
    """
    def __init__(self, path: str) -> None:
        ...

    @property
    def path(self) -> str:
        """
        PURPOSE:
        Path string.
        """
        ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("specifies 'init=False' and must not declare constructor '__init__'" in d.message for d in diags))

    def test_dataclass_init_true_without_constructor_rejected(self):
        spec = self.tmp / "init_true_missing_constructor.pyi"
        spec.write_text('''from dataclasses import dataclass
from framework import data_type

@dataclass(frozen=True)
@data_type
class MissingInit:
    """
    PURPOSE:
    Missing init constructor.
    """
    @property
    def val(self) -> int:
        """
        PURPOSE:
        Val.
        """
        ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("specifies 'init=True' (or default init) but does not declare constructor '__init__'" in d.message for d in diags))

    def test_variant_base_with_init_rejected(self):
        spec = self.tmp / "variant_base_with_init.pyi"
        spec.write_text('''from dataclasses import dataclass
from framework import data_type, variant

@dataclass(frozen=True)
@data_type
class BaseMsg:
    """
    PURPOSE:
    Base message.
    """
    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@variant
class SubMsg(BaseMsg):
    """
    PURPOSE:
    Sub message.
    """
    def __init__(self) -> None:
        ...
''')
        diags = lint_file(spec)
        self.assertTrue(any("Base data type 'BaseMsg' has variants and must" in d.message for d in diags))

    def test_variant_base_init_false_allowed(self):
        spec = self.tmp / "variant_base_init_false.pyi"
        spec.write_text('''from dataclasses import dataclass
from framework import data_type, variant

@dataclass(frozen=True, init=False)
@data_type
class BaseMsg:
    """
    PURPOSE:
    Base message.
    """
    ...

@dataclass(frozen=True)
@variant
class SubMsg(BaseMsg):
    """
    PURPOSE:
    Sub message.
    """
    def __init__(self) -> None:
        ...
''')
        diags = lint_file(spec)
        self.assertEqual(diags, [])


if __name__ == "__main__":
    unittest.main()

