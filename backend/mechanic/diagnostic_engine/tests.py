import unittest

from .matcher import DiagnosticEngine, MatchStatus
from .normalizer import normalize_text


class DiagnosticEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = DiagnosticEngine()

    def test_normalizes_common_starting_variations(self):
        self.assertEqual(normalize_text("CAR WON'T START!!!"), "car will not start")
        self.assertEqual(normalize_text("My vehicle doesn't start"), "my vehicle does not start")
        self.assertEqual(normalize_text("car won't turn on"), "car will not start")

    def test_starting_problem_needs_rule_specific_information(self):
        result = self.engine.match("My car will not start")
        self.assertEqual(result.status, MatchStatus.NEEDS_INFORMATION)
        self.assertEqual(result.matched_rule.rule_id, "no_start")
        self.assertIn("cranks", result.missing_information)
        self.assertIsNotNone(result.next_follow_up_question)

    def test_context_completes_follow_up_information(self):
        result = self.engine.match(
            "It will not start",
            {"matched_rule": "no_start", "answers": {"cranks": "no", "dashboard_lights": "yes", "clicking": "rapid", "battery_history": "yes"}},
        )
        self.assertEqual(result.status, MatchStatus.MATCHED)

    def test_keyword_groups_and_multiple_rules(self):
        result = self.engine.match("The brakes squeal and the steering wheel vibrates when braking")
        self.assertEqual(result.matched_rule.rule_id, "brake_noise")
        self.assertGreaterEqual(len(result.matched_rules), 2)

    def test_unsupported_query(self):
        result = self.engine.match("What is the weather today?")
        self.assertEqual(result.status, MatchStatus.UNSUPPORTED)

    def test_ambiguous_query_is_not_presented_as_a_diagnosis(self):
        result = self.engine.match("The steering wheel vibrates while braking")
        self.assertEqual(result.status, MatchStatus.AMBIGUOUS)

    def test_overheating_includes_safety_guidance(self):
        result = self.engine.match("The engine is overheating and steaming")
        self.assertEqual(result.matched_rule.rule_id, "engine_overheat")
        self.assertIn("Stop safely", result.safety_guidance)


if __name__ == "__main__":
    unittest.main()