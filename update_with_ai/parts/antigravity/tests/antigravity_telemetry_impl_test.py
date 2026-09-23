from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from update_with_ai.parts.antigravity.lib.antigravity_telemetry import ConversationStats
from update_with_ai.parts.antigravity.lib.antigravity_telemetry_impl import AntigravityTelemetry


class AntigravityTelemetryImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.telemetry = AntigravityTelemetry()

    def test_calculate_cost_gemini_38_flash(self) -> None:
        # Requirement: For `gemini-3.8-flash` pricing, rates apply fifty cents per million cached input tokens, two dollars per million fresh input tokens, and twelve dollars per million output tokens.
        cost = self.telemetry.calculate_cost(
            fresh_tokens=1_000_000,
            cached_tokens=2_000_000,
            output_tokens=500_000,
            model="gemini-3.8-flash",
        )
        # fresh: 1M * $2.00 = $2.00
        # cached: 2M * $0.50 = $1.00
        # output: 0.5M * $12.00 = $6.00
        # total: $9.00
        self.assertEqual(cost, 9.0)

    def test_calculate_cost_deepseek(self) -> None:
        # Requirement: For `deepseek` pricing, rates apply fourteen cents per million cached input tokens, twenty-eight cents per million fresh input tokens, and two dollars nineteen cents per million output tokens.
        cost = self.telemetry.calculate_cost(
            fresh_tokens=1_000_000,
            cached_tokens=1_000_000,
            output_tokens=1_000_000,
            model="deepseek",
        )
        # fresh: $0.28 + cached: $0.14 + output: $2.19 = $2.61
        self.assertEqual(cost, 2.61)

    def test_render_stats_table(self) -> None:
        # Requirement: The antigravity telemetry formats a collection of conversation stats records into a markdown table.
        # Requirement: Rendering a stats table constructs a formatted markdown table displaying agent name, turns, context, fresh input, cached input, hit percentage, output, and estimated cost dollars.
        s1 = ConversationStats(
            agent_name="Coordinator",
            turns=10,
            context_tokens=50_000,
            fresh_input_tokens=100_000,
            cached_input_tokens=900_000,
            cache_hit_percentage=90.0,
            output_tokens=5_000,
            estimated_cost_dollars=0.71,
        )
        table = self.telemetry.render_stats_table([s1])
        self.assertIn("| Agent / Worker | Turns | Context | Fresh Input | Cached Input | Hit % | Output | Cost (Gemini 3.8 Flash) |", table)
        self.assertIn("`Coordinator`", table)
        self.assertIn("90.0%", table)
        self.assertIn("**TOTAL**", table)

    @patch.object(AntigravityTelemetry, "get_conversation_stats")
    def test_check_context_cap(self, mock_get: MagicMock) -> None:
        # Requirement: The antigravity telemetry evaluates whether the context tokens of a conversation identifier exceed a specified threshold.
        # Requirement: Checking a context cap compares the conversation context tokens against the specified threshold, returning true when the context exceeds the threshold.
        mock_get.return_value = ConversationStats(
            agent_name="w1",
            turns=5,
            context_tokens=120_000,
            fresh_input_tokens=20_000,
            cached_input_tokens=100_000,
            cache_hit_percentage=83.3,
            output_tokens=1_000,
            estimated_cost_dollars=0.1,
        )
        self.assertTrue(self.telemetry.check_context_cap("w1", 100_000))
        self.assertFalse(self.telemetry.check_context_cap("w1", 200_000))


if __name__ == "__main__":
    unittest.main()
