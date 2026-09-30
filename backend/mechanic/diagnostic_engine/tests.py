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

    def test_normalizes_breaks_only_in_braking_failure_context(self):
        self.assertEqual(normalize_text("my breaks don't work"), "my brakes do not work")
        self.assertEqual(normalize_text("I take breaks at work"), "i take breaks at work")

    def test_brake_failure_initial_intent_never_enters_no_start(self):
        for message in (
            "my brakes don't work",
            "my breaks don't work",
            "my car brakes don't work",
            "my car breaks don't work",
            "the brakes aren't working",
            "my brakes stopped working",
            "I can't brake",
            "the car won't stop when I press the brakes",
            "brake pedal isn't working",
        ):
            with self.subTest(message=message):
                result = self.engine.match(message)
                self.assertEqual(result.matched_rule.rule_id, "brake_failure")
                self.assertNotEqual(result.matched_rule.rule_id, "no_start")
                self.assertIn("Do not drive", result.safety_guidance)

    def test_no_start_requires_explicit_starting_evidence(self):
        for message in ("my car won't start", "my engine won't start", "my car won't crank"):
            with self.subTest(message=message):
                self.assertEqual(self.engine.match(message).matched_rule.rule_id, "no_start")

    def test_started_vehicle_with_brake_failure_is_brake_intent(self):
        result = self.engine.match("my car starts but the brakes don't work")
        self.assertEqual(result.matched_rule.rule_id, "brake_failure")
        self.assertNotEqual(result.matched_rule.rule_id, "no_start")

    def test_component_complaint_matrix_selects_the_correct_domain(self):
        cases = (
            ("my steering wheel is broken", "steering_failure", "steering", "failure"),
            ("my steerinf wheel is broken", "steering_failure", "steering", "failure"),
            ("my steering wheel is shaking", "steering_vibration", "steering", "vibration"),
            ("the steering is vibrating", "steering_vibration", "steering", "vibration"),
            ("my tyre is not working", "tire_pressure", "tires", "failure"),
            ("my tire is flat", "tire_pressure", "tires", "flat"),
            ("my tire is punctured", "tire_pressure", "tires", "puncture_damage"),
            ("my tire pressure is low", "tire_pressure", "tires", "low_pressure"),
            ("my tire is damaged", "tire_pressure", "tires", "puncture_damage"),
            ("my battery isn't working", "battery_warning", "battery", "failure"),
            ("my battery is dead", "battery_warning", "battery", "failure"),
            ("my battery is weak", "battery_warning", "battery", "failure"),
            ("my engine is overheating", "engine_overheat", "engine", "overheating"),
            ("my engine makes a strange noise", "engine_noise", "engine", "noise"),
            ("my AC isn't cooling", "ac_not_cooling", "ac", "not_cooling"),
            ("my AC blows warm air", "ac_not_cooling", "ac", "not_cooling"),
            ("my steering wheel shakes", "steering_vibration", "steering", "vibration"),
            ("the car shakes when I brake", "brake_pull_vibration", "brakes", "vibration"),
        )
        for message, rule_id, component, complaint in cases:
            with self.subTest(message=message):
                result = self.engine.match(message)
                self.assertEqual(result.matched_rule.rule_id, rule_id)
                self.assertIn(component, result.components)
                self.assertIn(complaint, result.complaints)

    def test_generic_complaints_require_a_component(self):
        for message in ("my car isn't working", "something is wrong", "my vehicle has a problem", "it stopped working"):
            with self.subTest(message=message):
                result = self.engine.match(message)
                self.assertEqual(result.status, MatchStatus.NEEDS_INFORMATION)
                self.assertIsNone(result.matched_rule)
                self.assertEqual(result.missing_information, ("component",))

    def test_negation_is_preserved_for_engine_starting_intent(self):
        self.assertEqual(normalize_text("engine will not start"), "engine will not start")
        result = self.engine.match("my engine won't start")
        self.assertEqual(result.matched_rule.rule_id, "no_start")
        self.assertIn("no_start", result.complaints)

    def test_wheel_context_does_not_promote_steering_to_tire(self):
        result = self.engine.match("my steering wheel is broken")
        self.assertEqual(result.components, ("steering",))
        self.assertNotIn("tire_pressure", [item.rule.rule_id for item in result.matched_rules])

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
        self.assertTrue(result.next_follow_up_question.startswith("I couldn't determine that answer."))

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

    def test_starting_variations_share_no_start_semantics(self):
        for message in (
            "the car does not start",
            "it won't crank",
            "nothing happens when I turn the key",
            "the engine turns over but doesn't start",
            "my vehicle refuses to start",
        ):
            with self.subTest(message=message):
                result = self.engine.match(message)
                self.assertEqual(result.matched_rule.rule_id, "no_start")
                self.assertIn("no_start", result.complaints)

    def test_component_context_distinguishes_lights_brakes_and_wheels(self):
        cases = (
            ("headlights aren't working", "lights"),
            ("my brake light is broken", "lights"),
            ("my wheel is damaged", "tires"),
            ("the wheel shakes while braking", "tires"),
            ("the steering wheel shakes", "steering"),
        )
        for message, component in cases:
            with self.subTest(message=message):
                result = self.engine.match(message)
                self.assertIn(component, result.components)
                if component == "lights":
                    self.assertNotIn("brakes", result.components)

    def test_negated_observations_do_not_become_failures(self):
        result = self.engine.match("the battery is not dead")
        self.assertIn("battery", result.components)
        self.assertNotIn("failure", result.complaints)

        starting = self.engine.match("the engine will not start")
        self.assertIn("no_start", starting.complaints)

    def test_generic_and_non_automotive_complaints_have_different_routes(self):
        for message in ("my car is broken", "something is wrong", "it stopped working"):
            with self.subTest(message=message):
                result = self.engine.match(message)
                self.assertEqual(result.status, MatchStatus.NEEDS_INFORMATION)
                self.assertEqual(result.missing_information, ("component",))

        for message in ("my laptop is broken", "my computer is overheating", "my washing machine isn't working"):
            with self.subTest(message=message):
                self.assertEqual(self.engine.match(message).status, MatchStatus.UNSUPPORTED)

    def test_unknown_automotive_components_are_clarified_without_inventing_rules(self):
        for message, component in (("my horn stopped working", "horn"), ("my wipers are broken", "wipers")):
            with self.subTest(message=message):
                result = self.engine.match(message)
                self.assertEqual(result.status, MatchStatus.NEEDS_INFORMATION)
                self.assertIsNone(result.matched_rule)
                self.assertIn(component, result.components)

    def test_multi_component_message_preserves_safety_critical_brakes(self):
        result = self.engine.match("the car starts but the brakes don't work and the steering pulls")
        self.assertEqual(result.matched_rule.rule_id, "brake_failure")
        self.assertIn("Do not drive", result.safety_guidance)


if __name__ == "__main__":
    unittest.main()