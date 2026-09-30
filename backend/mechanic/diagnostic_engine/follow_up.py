"""Context-aware interpretation of answers to diagnostic follow-up questions."""

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Any

from .normalizer import normalize_text
from .rules import DiagnosticRule


@dataclass(frozen=True)
class FollowUpInterpretation:
    answered: bool
    value: str | None
    facts: dict[str, Any]
    confidence: float


class FollowUpInterpreter:
    """Map a reply to the semantic field currently being asked about."""

    _AFFIRMATIVE = {"yes", "yeah", "yep", "correct", "right", "true"}
    _NEGATIVE = {"no", "nope", "nah", "false"}
    _UNCERTAIN = {"maybe", "unsure", "uncertain", "sometimes", "occasionally"}
    _NEGATION = {
        "no",
        "not",
        "never",
        "nothing",
        "without",
        "doesnt",
        "didnt",
        "wont",
    }

    def interpret(
        self,
        message: str,
        rule: DiagnosticRule,
        key: str,
    ) -> FollowUpInterpretation:
        normalized = normalize_text(message)

        if not normalized:
            return FollowUpInterpretation(False, None, {}, 0.0)

        concepts = rule.follow_up_semantics.get(key, {})
        tokens = normalized.split()
        direct = self._score_concepts(normalized, concepts)
        polarity = self._polarity(tokens)

        if polarity == "uncertain" and not direct:
            return FollowUpInterpretation(
                True,
                "uncertain",
                {key: "uncertain"},
                0.82,
            )

        if direct:
            value, score = max(
                direct.items(),
                key=lambda item: item[1],
            )

            tied = [
                item
                for item, item_score in direct.items()
                if score - item_score < 0.35
            ]

            if len(tied) > 1:
                categorical = [
                    item
                    for item in tied
                    if item not in {
                        "affirmative",
                        "negative",
                        "changed",
                        "normal",
                    }
                ]

                if categorical and len(categorical) == len(tied):
                    value = "/".join(sorted(categorical))
                else:
                    return FollowUpInterpretation(
                        False,
                        None,
                        {},
                        0.35,
                    )

            if polarity == "negative" and self._negates_value(
                normalized,
                concepts[value],
            ):
                normal_values = [
                    candidate
                    for candidate in concepts
                    if candidate in {"normal", "negative"}
                ]

                if normal_values:
                    value = normal_values[0]

            facts = {key: value}

            return FollowUpInterpretation(
                True,
                value,
                facts,
                min(0.99, 0.62 + score / 4),
            )

        if polarity in {"affirmative", "negative"}:
            if self._is_binary(rule, key):
                return FollowUpInterpretation(
                    True,
                    polarity,
                    {key: polarity},
                    0.9,
                )

            # A bare yes/no answer can still answer the currently
            # pending follow-up question even when the rule does not
            # explicitly define affirmative/negative concepts for
            # that field.
            question = rule.follow_up_questions.get(key, "")

            if question:
                question_tokens = {
                    term
                    for term in re.findall(
                        r"[a-z0-9]+",
                        normalize_text(question),
                    )
                    if len(term) > 3
                }

                if question_tokens:
                    return FollowUpInterpretation(
                        True,
                        polarity,
                        {key: polarity},
                        0.85,
                    )

        if self._matches_question(
            normalized,
            rule.follow_up_questions.get(key, ""),
        ):
            value = polarity or "provided"

            return FollowUpInterpretation(
                True,
                value,
                {key: value},
                0.72,
            )

        return FollowUpInterpretation(
            False,
            None,
            {},
            0.0,
        )

    def _score_concepts(
        self,
        text: str,
        concepts: dict[str, tuple[str, ...]],
    ) -> dict[str, float]:
        scores: dict[str, float] = {}

        for value, terms in concepts.items():
            score = 0.0

            for term in terms:
                normalized_term = normalize_text(term)

                if re.search(
                    rf"\b{re.escape(normalized_term)}\b",
                    text,
                ):
                    if not self._negates_value(
                        text,
                        (normalized_term,),
                    ):
                        score = max(
                            score,
                            1.0 + min(
                                len(normalized_term.split()),
                                3,
                            ) * 0.1,
                        )

                elif self._has_typo_match(
                    normalized_term,
                    text,
                ):
                    score = max(score, 0.75)

            if score:
                scores[value] = score

        return scores

    def _has_typo_match(
        self,
        term: str,
        text: str,
    ) -> bool:
        if " " in term:
            return False

        return any(
            len(word) >= 4
            and SequenceMatcher(
                None,
                term,
                word,
            ).ratio() >= 0.82
            for word in text.split()
        )

    def _polarity(
        self,
        tokens: list[str],
    ) -> str | None:
        if any(token in self._UNCERTAIN for token in tokens):
            return "uncertain"

        if tokens and tokens[0] in self._AFFIRMATIVE:
            return "affirmative"

        if tokens and tokens[0] in self._NEGATIVE:
            return "negative"

        if tokens and tokens[0] in self._NEGATION:
            return "negative"

        return None

    def _negates_value(
        self,
        text: str,
        terms: tuple[str, ...],
    ) -> bool:
        tokens = text.split()

        for term in terms:
            term_tokens = normalize_text(term).split()

            for index in range(
                len(tokens) - len(term_tokens) + 1
            ):
                if tokens[
                    index:index + len(term_tokens)
                ] == term_tokens:
                    window = tokens[
                        max(0, index - 2):index
                    ]

                    if any(
                        token in self._NEGATION
                        for token in window
                    ):
                        return True

                    if (
                        "or" in window
                        and any(
                            token in self._NEGATION
                            for token in tokens[:index]
                        )
                    ):
                        return True

        return False

    def _is_binary(
        self,
        rule: DiagnosticRule,
        key: str,
    ) -> bool:
        concepts = rule.follow_up_semantics.get(key, {})

        return bool(
            {"affirmative", "negative"} & concepts.keys()
        ) or key in rule.yes_no_follow_up_keys

    def _matches_question(
        self,
        message: str,
        question: str,
    ) -> bool:
        question_terms = {
            term
            for term in re.findall(
                r"[a-z0-9]+",
                normalize_text(question),
            )
            if len(term) > 3
        }

        return bool(
            question_terms & set(message.split())
        )