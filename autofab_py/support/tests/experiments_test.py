"""Unit tests for support.lib.experiments."""

from __future__ import annotations

import os
import unittest
from support.lib import experiments


class ExperimentsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_env = os.environ.get("AUTOFAB_EXPERIMENT")
        experiments.clear_active_experiments()

    def tearDown(self) -> None:
        if self._orig_env is not None:
            os.environ["AUTOFAB_EXPERIMENT"] = self._orig_env
            experiments.set_active_experiments(self._orig_env)
        else:
            os.environ.pop("AUTOFAB_EXPERIMENT", None)
            experiments.clear_active_experiments()

    def test_default_empty(self) -> None:
        os.environ.pop("AUTOFAB_EXPERIMENT", None)
        experiments.clear_active_experiments()
        self.assertEqual(experiments.get_active_experiments(), set())
        self.assertFalse(experiments.is_experiment_active("structured_blame"))

    def test_single_experiment(self) -> None:
        experiments.set_active_experiments("structured_blame")
        self.assertEqual(experiments.get_active_experiments(), {"structured_blame"})
        self.assertTrue(experiments.is_experiment_active("structured_blame"))
        self.assertTrue(experiments.is_experiment_active("STRUCTURED_BLAME"))
        self.assertFalse(experiments.is_experiment_active("other"))

    def test_multiple_experiments(self) -> None:
        experiments.set_active_experiments("exp1, exp2, EXP3")
        self.assertEqual(experiments.get_active_experiments(), {"exp1", "exp2", "exp3"})
        self.assertTrue(experiments.is_experiment_active("exp1"))
        self.assertTrue(experiments.is_experiment_active("exp2"))
        self.assertTrue(experiments.is_experiment_active("exp3"))
        self.assertFalse(experiments.is_experiment_active("exp4"))

    def test_boolean_aliases(self) -> None:
        for val in ["0", "false", "no", "none", "off", ""]:
            experiments.set_active_experiments(val)
            self.assertEqual(experiments.get_active_experiments(), set())
            self.assertFalse(experiments.is_experiment_active("structured_blame"))

    def test_environment_variable_fallback(self) -> None:
        experiments.clear_active_experiments()
        os.environ["AUTOFAB_EXPERIMENT"] = "custom_exp"
        self.assertTrue(experiments.is_experiment_active("custom_exp"))
        self.assertEqual(experiments.get_active_experiments(), {"custom_exp"})


if __name__ == "__main__":
    unittest.main()
