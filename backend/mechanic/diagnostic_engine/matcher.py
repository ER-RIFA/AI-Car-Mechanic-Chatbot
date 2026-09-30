"""Explainable weighted matching for the automotive diagnostic rules."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .normalizer import normalize_text, text_from_context
from .follow_up import FollowUpInterpreter
from .rules import DIAGNOSTIC_RULES, DiagnosticRule
from .semantics import RULE_INTENTS, SemanticEvidence, extract_semantics


_NON_AUTOMOTIVE_CONTEXT = {
    "laptop", "phone", "computer", "washing machine", "refrigerator", "oven", "television",
}
_COMPONENT_FOLLOW_UP_RULE = "__component_follow_up__"
_COMPONENT_FOLLOW_UP_KEY = "component_details"
_FOLLOW_UP_CONTEXT_TERMS = {
    "when", "while", "after", "before", "press", "pressed", "sound", "noise", "silent",
    "click", "clicking", "come", "comes", "only", "both", "one", "left", "right",
    "sometimes", "always", "intermittent", "intermittently", "completely", "not at all",
}


class MatchStatus(str, Enum):
    MATCHED = "matched"
    NEEDS_INFORMATION = "needs_information"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RuleMatch:
    rule: DiagnosticRule
    score: int
    matched_groups: tuple[str, ...]


@dataclass(frozen=True)
class DiagnosticMatchResult:
    status: MatchStatus
    matched_rule: DiagnosticRule | None
    matched_rules: tuple[RuleMatch, ...]
    collected_symptoms: tuple[str, ...]
    missing_information: tuple[str, ...]
    next_follow_up_question: str | None
    possible_diagnoses: tuple[str, ...]
    recommended_service: str | None
    safety_guidance: str | None
    match_score: int | None
    components: tuple[str, ...] = ()
    complaints: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Return an API-neutral representation suitable for a later service layer."""
        return {
            "status": self.status.value,
            "matched_rule": self.matched_rule.rule_id if self.matched_rule else None,
            "matched_rules": [
                {"rule_id": item.rule.rule_id, "score": item.score, "matched_groups": item.matched_groups}
                for item in self.matched_rules
            ],
            "collected_symptoms": self.collected_symptoms,
            "missing_information": self.missing_information,
            "next_follow_up_question": self.next_follow_up_question,
            "possible_diagnoses": self.possible_diagnoses,
            "recommended_service": self.recommended_service,
            "safety_guidance": self.safety_guidance,
            "match_score": self.match_score,
            "components": self.components,
            "complaints": self.complaints,
        }


class DiagnosticEngine:
    """Match messages to deterministic rules without persistence or HTTP concerns."""

    def __init__(self, rules: tuple[DiagnosticRule, ...] = DIAGNOSTIC_RULES) -> None:
        self.rules = rules
        self.follow_up_interpreter = FollowUpInterpreter()

    def match(self, message: str, context: dict[str, Any] | None = None) -> DiagnosticMatchResult:
        context = context if isinstance(context, dict) else {}
        context.setdefault("follow_up_answers", {})
        normalized_message = normalize_text(message)
        pending_answer = self.update_follow_up_context(message, context)
        domain_reclassified = context.pop("_domain_reclassified", False)
        normalized_context = "" if domain_reclassified else text_from_context(context)
        answer_was_pending = pending_answer is True
        combined_text = normalize_text(
            f"{'' if answer_was_pending else normalized_message} {normalized_context}"
        )
        evidence = extract_semantics(combined_text)
        matches = sorted(
            (self._score_rule(rule, combined_text, context, evidence) for rule in self.rules),
            key=lambda item: item.score,
            reverse=True,
        )
        matches = tuple(item for item in matches if item.score > 0)
        if not matches:
            if any(term in normalized_message for term in _NON_AUTOMOTIVE_CONTEXT):
                return DiagnosticMatchResult(MatchStatus.UNSUPPORTED, None, (), (), (), None, (), None, None, None)
            if evidence.components or evidence.complaints:
                component = evidence.interpretation.component
                answered_component_follow_up = context.get("_component_follow_up_answered")
                missing = ("component_behavior",) if answered_component_follow_up else (
                    ("complaint",) if component else ("component",)
                )
                question = (
                    f"Does the {component.replace('_', ' ')} work intermittently, or is it completely inactive?"
                    if component and answered_component_follow_up
                    else f"What is happening with the {component.replace('_', ' ')} system?"
                    if component
                    else "Which vehicle component or system is affected?"
                )
                return DiagnosticMatchResult(
                    MatchStatus.NEEDS_INFORMATION, None, (), (), missing,
                    question, (), None, None, None,
                    tuple(evidence.components), tuple(evidence.complaints),
                )
            return DiagnosticMatchResult(MatchStatus.UNSUPPORTED, None, (), (), (), None, (), None, None, None)

        primary = matches[0]
        if len(matches) > 1 and primary.score - matches[1].score <= 1 and matches[1].score >= 3:
            return DiagnosticMatchResult(
                MatchStatus.AMBIGUOUS, primary.rule, matches[:3], primary.matched_groups, (), None,
                primary.rule.possible_diagnoses, primary.rule.recommended_service, primary.rule.safety_guidance, primary.score,
                tuple(evidence.components), tuple(evidence.complaints),
            )

        missing = tuple(
            key for key in primary.rule.required_information
            if not self._has_information(primary.rule, key, combined_text, context)
        )
        status = MatchStatus.NEEDS_INFORMATION if missing else MatchStatus.MATCHED
        next_question = primary.rule.follow_up_questions[missing[0]] if missing else None
        if answer_was_pending and missing:
            next_question = f"I couldn't determine that answer. Could you clarify: {next_question}"
        return DiagnosticMatchResult(
            status, primary.rule, matches[:3], primary.matched_groups, missing,
            next_question,
            primary.rule.possible_diagnoses, primary.rule.recommended_service,
            primary.rule.safety_guidance, primary.score,
            tuple(evidence.components), tuple(evidence.complaints),
        )

    def update_follow_up_context(self, message: str, context: dict[str, Any]) -> bool | None:
        """Interpret a pending answer before considering standalone symptoms."""
        normalized_message = normalize_text(message)
        pending = context.get("pending_follow_up")
        if isinstance(pending, dict) and pending.get("rule_id") == _COMPONENT_FOLLOW_UP_RULE:
            evidence = extract_semantics(message)
            component = pending.get("component")
            has_component_evidence = isinstance(component, str) and component in evidence.components
            has_context_evidence = any(
                term in normalized_message.split() or term in normalized_message
                for term in _FOLLOW_UP_CONTEXT_TERMS
            )
            if has_component_evidence or evidence.complaints or has_context_evidence:
                self._accumulate_answer(
                    context,
                    _COMPONENT_FOLLOW_UP_KEY,
                    message,
                )
                context.setdefault("follow_up_facts", {}).update({
                    "component": component,
                    "details_provided": True,
                })
                context.pop("pending_follow_up", None)
                context["_component_follow_up_answered"] = True
                return True
            return False
        rule_id = pending.get("rule_id") if isinstance(pending, dict) else context.get("matched_rule")
        key = pending.get("key") if isinstance(pending, dict) else None
        rule = next((item for item in self.rules if item.rule_id == rule_id), None)
        if rule is None:
            return None

        answers = context.setdefault("follow_up_answers", {})
        if not isinstance(answers, dict):
            return None
        if isinstance(key, str):
            profile = RULE_INTENTS.get(rule.rule_id)
            new_components = set(extract_semantics(message).components)
            if profile and new_components and not new_components.intersection(
                (*profile.components, *profile.related_components)
            ):
                context.pop("pending_follow_up", None)
                context.pop("matched_rule", None)
                context["_domain_reclassified"] = True
                return False
            interpretation = self.follow_up_interpreter.interpret(message, rule, key)
            if isinstance(pending, dict):
                if interpretation.answered:
                    self._accumulate_answer(context, key, interpretation.value or message)
                    context.setdefault("follow_up_facts", {}).update(interpretation.facts)
                return True

        for field, signals in rule.information_signals.items():
            if field not in answers:
                signal = next((signal for signal in signals if signal in normalized_message), None)
                if signal:
                    answers[field] = signal
        return False

    def _accumulate_answer(self, context: dict[str, Any], key: str, value: str) -> None:
        answers = context.setdefault("follow_up_answers", {})
        previous = answers.get(key)
        if previous is None or previous == value:
            answers[key] = value
            return
        history = context.setdefault("follow_up_answer_history", {}).setdefault(key, [])
        if not history:
            history.append(previous)
        history.append(value)
        answers[key] = list(history)

    def _score_rule(
        self,
        rule: DiagnosticRule,
        text: str,
        context: dict[str, Any],
        evidence: SemanticEvidence,
    ) -> RuleMatch:
        profile = RULE_INTENTS.get(rule.rule_id)
        pending_current_rule = (
            isinstance(context.get("pending_follow_up"), dict)
            and context["pending_follow_up"].get("rule_id") == rule.rule_id
        )
        if profile:
            if not pending_current_rule and not all(item in evidence.components for item in profile.required_components):
                return RuleMatch(rule, 0, ())
            if not pending_current_rule and not all(item in evidence.complaints for item in profile.required_complaints):
                return RuleMatch(rule, 0, ())
            if not pending_current_rule and profile.complaint_options and not any(
                item in evidence.complaints for item in profile.complaint_options
            ):
                return RuleMatch(rule, 0, ())
        matched_groups = tuple(
            group for group, aliases in rule.keyword_groups.items()
            if any(alias in text for alias in aliases)
        )
        if rule.required_keyword_groups and not pending_current_rule and not all(
            group in matched_groups for group in rule.required_keyword_groups
        ):
            return RuleMatch(rule, 0, matched_groups)
        score = 2 * len(matched_groups)
        if profile:
            score += 2 * sum(item in evidence.components for item in profile.components)
            score += 3 * sum(item in evidence.complaints for item in profile.complaints)
            score += sum(evidence.components.get(item, 0) for item in profile.components)
            if rule.rule_id == "no_start" and "no_start" in evidence.complaints:
                score += 4
        if len(matched_groups) >= 2:
            score += len(matched_groups) - 1
        if self._context_mentions_rule(context, rule.rule_id):
            score += 2
        return RuleMatch(rule, score, matched_groups)

    def _context_mentions_rule(self, context: object, rule_id: str) -> bool:
        if not isinstance(context, dict):
            return False
        for key, value in context.items():
            if key in ("matched_rule", "rule_id", "symptom_rule") and str(value) == rule_id:
                return True
            if isinstance(value, dict) and self._context_mentions_rule(value, rule_id):
                return True
        return False

    def _has_information(self, rule: DiagnosticRule, key: str, text: str, context: dict[str, Any]) -> bool:
        if self._context_has_key(context, key):
            return True
        return any(signal in text for signal in rule.information_signals[key])

    def _context_has_key(self, context: object, key: str) -> bool:
        if not isinstance(context, dict):
            return False
        for context_key, value in context.items():
            if context_key == key and value not in (None, "", [], {}, False):
                return True
            if isinstance(value, dict) and self._context_has_key(value, key):
                return True
        return False