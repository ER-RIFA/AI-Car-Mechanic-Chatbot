import unittest

from .matcher import DiagnosticEngine


class ConversationalFollowUpTests(unittest.TestCase):
    """Natural-language follow-up corpus; assertions target semantic state."""

    CASES = (
        ("no_start", "cranks", "yes", True),
        ("no_start", "cranks", "nope, it just clicks", True),
        ("no_start", "cranks", "the engine turns over but doesn't start", True),
        ("no_start", "cranks", "nothing happens", True),
        ("no_start", "cranks", "it cranks normally", True),
        ("no_start", "dashboard_lights", "yeah, the dash lights come on", True),
        ("no_start", "dashboard_lights", "no, everything stays dark", True),
        ("no_start", "clicking", "there is a rapid clicking sound", True),
        ("starting_click", "click_pattern", "just one solid click", True),
        ("starting_click", "click_pattern", "it is a rapid series", True),
        ("starting_click", "click_pattern", "only a tiny click", True),
        ("engine_overheat", "temperature", "the gauge is nearly in the red", True),
        ("engine_overheat", "temperature", "temperature looks normal", True),
        ("engine_overheat", "coolant_or_leak", "nope, the coolant level is fine", True),
        ("engine_overheat", "coolant_or_leak", "yes, coolant is leaking", True),
        ("engine_overheat", "warning_signs", "there is steam and a hot smell", True),
        ("engine_overheat", "warning_signs", "no smoke or steam", True),
        ("brake_noise", "noise_type", "just a small squeak", True),
        ("brake_noise", "noise_type", "sounds like metal scraping", True),
        ("brake_noise", "noise_type", "pretty harsh grinding", True),
        ("brake_noise", "braking_effect", "no, braking feels normal", True),
        ("brake_noise", "braking_effect", "yeah, it takes longer to stop", True),
        ("brake_noise", "braking_effect", "the pedal sinks and feels soft", True),
        ("brake_noise", "braking_effect", "not really", True),
        ("brake_noise", "braking_effect", "the pedal feels harder", True),
        ("tire_pressure", "affected_tire", "the driver side front tire", True),
        ("tire_pressure", "visible_damage", "no, I cannot see any damage", True),
        ("tire_pressure", "visible_damage", "there is a screw in it", True),
        ("tire_pressure", "pressure_reading", "it reads 28 psi", True),
        ("battery_warning", "warning_behavior", "yes, the charging light stays on", True),
        ("battery_warning", "starting_behavior", "starting is slow and intermittent", True),
        ("battery_warning", "electrical_symptoms", "the lights flicker and the radio resets", True),
        ("battery_warning", "electrical_symptoms", "everything electrical is normal", True),
        ("brake_noise", "braking_effect", "the weather is sunny", False),
        ("engine_overheat", "coolant_or_leak", "I am not sure, maybe", True),
        ("starting_click", "click_pattern", "the brakes feel soft", False),
    )

    def setUp(self):
        self.engine = DiagnosticEngine()

    def _context(self, rule_id, key):
        rule = next(rule for rule in self.engine.rules if rule.rule_id == rule_id)
        answers = {field: "already answered" for field in rule.required_information if field != key}
        return {
            "matched_rule": rule_id,
            "pending_follow_up": {"rule_id": rule_id, "key": key},
            "follow_up_answers": answers,
        }

    def test_natural_language_dataset_updates_only_pending_field(self):
        for rule_id, key, answer, recognized in self.CASES:
            with self.subTest(rule_id=rule_id, key=key, answer=answer):
                context = self._context(rule_id, key)
                previous = dict(context["follow_up_answers"])
                result = self.engine.match(answer, context)
                self.assertEqual(key in context["follow_up_answers"], recognized)
                for field, value in previous.items():
                    self.assertEqual(context["follow_up_answers"][field], value)
                if recognized:
                    self.assertNotEqual(result.next_follow_up_question, result.matched_rule.follow_up_questions[key])
                else:
                    self.assertNotEqual(result.next_follow_up_question, result.matched_rule.follow_up_questions[key] if result.matched_rule else None)

    def test_contradictory_answer_is_retained_as_history(self):
        context = self._context("brake_noise", "braking_effect")
        context["follow_up_answers"]["braking_effect"] = "normal"
        self.engine.match("yes, braking is different", context)
        self.assertEqual(context["follow_up_answers"]["braking_effect"], ["normal", "changed"])
        self.assertEqual(context["follow_up_answer_history"]["braking_effect"], ["normal", "changed"])

    def test_multi_turn_starting_conversation_advances_without_reasking(self):
        context = {}
        first = self.engine.match("my car will not start", context)
        self.assertEqual(first.matched_rule.rule_id, "no_start")
        context.update({
            "matched_rule": "no_start",
            "pending_follow_up": {"rule_id": "no_start", "key": "cranks"},
            "follow_up_answers": {},
        })
        self.engine.match("it just clicks", context)
        self.assertIn("cranks", context["follow_up_answers"])
        self.assertNotEqual(context["follow_up_answers"]["cranks"], "")

    def test_multi_turn_brake_conversation_preserves_each_answer(self):
        context = self._context("brake_noise", "noise_type")
        self.engine.match("light squealing", context)
        context["follow_up_answers"].pop("braking_effect", None)
        context["pending_follow_up"] = {"rule_id": "brake_noise", "key": "braking_effect"}
        self.engine.match("the pedal feels soft", context)
        self.assertEqual(context["follow_up_answers"]["noise_type"], "light")
        self.assertEqual(context["follow_up_answers"]["braking_effect"], "changed")
        self.assertNotIn("noise_type", context.get("pending_follow_up", {}).get("key", ""))

    def test_multi_turn_overheating_conversation_preserves_each_answer(self):
        context = self._context("engine_overheat", "temperature")
        self.engine.match("the gauge is in the red", context)
        context["follow_up_answers"].pop("coolant_or_leak", None)
        context["pending_follow_up"] = {"rule_id": "engine_overheat", "key": "coolant_or_leak"}
        self.engine.match("no coolant leak", context)
        context["follow_up_answers"].pop("warning_signs", None)
        context["pending_follow_up"] = {"rule_id": "engine_overheat", "key": "warning_signs"}
        self.engine.match("there is steam", context)
        self.assertEqual(context["follow_up_answers"]["temperature"], "high")
        self.assertEqual(context["follow_up_answers"]["coolant_or_leak"], "negative")
        self.assertEqual(context["follow_up_answers"]["warning_signs"], "affirmative")

    def test_multi_turn_tire_conversation_preserves_each_answer(self):
        context = self._context("tire_pressure", "affected_tire")
        self.engine.match("front left tire", context)
        context["follow_up_answers"].pop("visible_damage", None)
        context["pending_follow_up"] = {"rule_id": "tire_pressure", "key": "visible_damage"}
        self.engine.match("no visible damage", context)
        context["follow_up_answers"].pop("pressure_reading", None)
        context["pending_follow_up"] = {"rule_id": "tire_pressure", "key": "pressure_reading"}
        self.engine.match("it reads 30 psi", context)
        self.assertEqual(context["follow_up_answers"]["affected_tire"], "front/left")
        self.assertEqual(context["follow_up_answers"]["visible_damage"], "negative")
        self.assertEqual(context["follow_up_answers"]["pressure_reading"], "provided")

    def test_multi_turn_battery_conversation_preserves_each_answer(self):
        context = self._context("battery_warning", "warning_behavior")
        self.engine.match("yes, it stays on", context)
        context["follow_up_answers"].pop("starting_behavior", None)
        context["pending_follow_up"] = {"rule_id": "battery_warning", "key": "starting_behavior"}
        self.engine.match("starting is slow", context)
        context["follow_up_answers"].pop("electrical_symptoms", None)
        context["pending_follow_up"] = {"rule_id": "battery_warning", "key": "electrical_symptoms"}
        self.engine.match("the lights flicker", context)
        self.assertEqual(context["follow_up_answers"]["warning_behavior"], "on")
        self.assertEqual(context["follow_up_answers"]["starting_behavior"], "slow")
        self.assertEqual(context["follow_up_answers"]["electrical_symptoms"], "changed")

    def test_unrelated_pending_answer_is_not_sent_to_global_matcher(self):
        context = self._context("brake_noise", "braking_effect")
        result = self.engine.match("the engine is overheating", context)
        self.assertNotIn("braking_effect", context["follow_up_answers"])
        self.assertEqual(result.matched_rule.rule_id, "engine_overheat")

    def test_conflicting_steering_answer_invalidates_pending_tire_domain(self):
        context = {
            "matched_rule": "tire_pressure",
            "pending_follow_up": {"rule_id": "tire_pressure", "key": "affected_tire"},
            "follow_up_answers": {},
        }
        result = self.engine.match("steering wheel", context)

        self.assertIsNone(result.matched_rule)
        self.assertEqual(result.status.value, "needs_information")
        self.assertIn("steering", result.next_follow_up_question.lower())
        self.assertNotIn("affected_tire", context["follow_up_answers"])
        self.assertNotIn("pending_follow_up", context)

    def test_tire_answer_can_switch_a_pending_steering_domain(self):
        context = {
            "matched_rule": "steering_vibration",
            "pending_follow_up": {"rule_id": "steering_vibration", "key": "speed"},
            "follow_up_answers": {},
        }
        result = self.engine.match("front left tire", context)

        self.assertEqual(result.matched_rule.rule_id, "tire_pressure")
        self.assertEqual(result.status.value, "needs_information")
        self.assertIn("puncture", result.next_follow_up_question.lower())
        self.assertNotIn("speed", context["follow_up_answers"])


if __name__ == "__main__":
    unittest.main()