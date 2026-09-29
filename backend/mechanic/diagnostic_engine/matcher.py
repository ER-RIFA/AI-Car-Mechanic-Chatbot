"""Explainable weighted matching for the automotive diagnostic rules."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .normalizer import normalize_text, text_from_context
from .rules import DIAGNOSTIC_RULES, DiagnosticRule


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
        }


class DiagnosticEngine:
    """Match messages to deterministic rules without persistence or HTTP concerns."""

    def __init__(self, rules: tuple[DiagnosticRule, ...] = DIAGNOSTIC_RULES) -> None:
        self.rules = rules

    def match(self, message: str, context: dict[str, Any] | None = None) -> DiagnosticMatchResult:
        normalized_message = normalize_text(message)
        normalized_context = text_from_context(context or {})
        combined_text = normalize_text(f"{normalized_message} {normalized_context}")
        matches = sorted(
            (self._score_rule(rule, combined_text, context or {}) for rule in self.rules),
            key=lambda item: item.score,
            reverse=True,
        )
        matches = tuple(item for item in matches if item.score > 0)
        if not matches:
            return DiagnosticMatchResult(MatchStatus.UNSUPPORTED, None, (), (), (), None, (), None, None, None)

        primary = matches[0]
        if len(matches) > 1 and primary.score - matches[1].score <= 1 and matches[1].score >= 3:
            return DiagnosticMatchResult(
                MatchStatus.AMBIGUOUS, primary.rule, matches[:3], primary.matched_groups, (), None,
                primary.rule.possible_diagnoses, primary.rule.recommended_service, primary.rule.safety_guidance, primary.score,
            )

        missing = tuple(
            key for key in primary.rule.required_information
            if not self._has_information(primary.rule, key, combined_text, context or {})
        )
        status = MatchStatus.NEEDS_INFORMATION if missing else MatchStatus.MATCHED
        return DiagnosticMatchResult(
            status, primary.rule, matches[:3], primary.matched_groups, missing,
            primary.rule.follow_up_questions[missing[0]] if missing else None,
            primary.rule.possible_diagnoses, primary.rule.recommended_service,
            primary.rule.safety_guidance, primary.score,
        )

    def _score_rule(self, rule: DiagnosticRule, text: str, context: dict[str, Any]) -> RuleMatch:
        matched_groups = tuple(
            group for group, aliases in rule.keyword_groups.items()
            if any(alias in text for alias in aliases)
        )
        score = 2 * len(matched_groups)
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