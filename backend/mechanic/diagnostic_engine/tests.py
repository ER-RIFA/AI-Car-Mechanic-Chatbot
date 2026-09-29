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

    def test_brake_follow_up_accepts_natural_language_answer(self):
        context = {
            "matched_rule": "brake_noise",
            "pending_follow_up": {"rule_id": "brake_noise", "key": "braking_effect"},
            "follow_up_answers": {"noise_type": "squeal", "recent_brake_work": "provided"},
        }
        result = self.engine.match("breaking is a bit hard", context)

        self.assertEqual(result.status, MatchStatus.MATCHED)

    def test_brake_follow_up_accepts_harder_brakes_and_hard_pedal(self):
        for answer in ("the brakes feel harder", "the pedal feels hard"):
            with self.subTest(answer=answer):
                result = self.engine.match(answer, {
                    "matched_rule": "brake_noise",
                    "pending_follow_up": {"rule_id": "brake_noise", "key": "braking_effect"},
                    "follow_up_answers": {"noise_type": "squeal", "recent_brake_work": "provided"},
                })
                self.assertEqual(result.status, MatchStatus.MATCHED)

    def test_brake_follow_up_accepts_normal_and_soft_pedal_answers(self):
        for answer in ("braking feels normal", "the pedal feels soft"):
            with self.subTest(answer=answer):
                result = self.engine.match(answer, {
                    "matched_rule": "brake_noise",
                    "pending_follow_up": {"rule_id": "brake_noise", "key": "braking_effect"},
                    "follow_up_answers": {"noise_type": "squeal", "recent_brake_work": "provided"},
                })
                self.assertEqual(result.status, MatchStatus.MATCHED)

    def test_brake_follow_up_accepts_scoped_yes_no_answers(self):
        for answer in ("no", "no it doesn't", "no, braking feels normal", "yes", "yes, braking feels harder"):
            with self.subTest(answer=answer):
                result = self.engine.match(answer, {
                    "matched_rule": "brake_noise",
                    "pending_follow_up": {"rule_id": "brake_noise", "key": "braking_effect"},
                    "follow_up_answers": {"noise_type": "squeal", "recent_brake_work": "provided"},
                })
                self.assertEqual(result.status, MatchStatus.MATCHED)
                self.assertIsNone(result.next_follow_up_question)

    def test_follow_up_answers_accumulate_across_pending_fields(self):
        context = {
            "matched_rule": "brake_noise",
            "pending_follow_up": {"rule_id": "brake_noise", "key": "braking_effect"},
            "follow_up_answers": {"noise_type": "light squeal"},
        }

        first = self.engine.match("no", context)
        self.assertEqual(context["follow_up_answers"]["braking_effect"], "negative")
        self.assertNotEqual(first.next_follow_up_question, "Has braking performance changed or does the pedal feel soft?")

        context["pending_follow_up"] = {"rule_id": "brake_noise", "key": "recent_brake_work"}
        self.engine.match("no", context)
        self.assertEqual(
            context["follow_up_answers"],
            {
                "noise_type": "light squeal",
                "braking_effect": "negative",
                "recent_brake_work": "negative",
            },
        )

    def test_unrelated_pending_brake_answer_is_not_interpreted(self):
        result = self.engine.match("the radio is louder", {
            "matched_rule": "brake_noise",
            "pending_follow_up": {"rule_id": "brake_noise", "key": "braking_effect"},
            "follow_up_answers": {"noise_type": "squeal", "recent_brake_work": "provided"},
        })

        self.assertEqual(result.status, MatchStatus.NEEDS_INFORMATION)
        self.assertEqual(result.next_follow_up_question, "Has braking performance changed or does the pedal feel soft?")

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