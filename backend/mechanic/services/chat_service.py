import json
import uuid
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from mechanic.diagnostic_engine import DiagnosticEngine, MatchStatus
from mechanic.diagnostic_engine.normalizer import normalize_text
from mechanic.diagnostic_engine.rules import DiagnosticRule

from ..models import Conversation, Diagnosis, Message
from .gemini_service import GeminiDiagnosticResult, GeminiService, GeminiServiceError


UNSUPPORTED_REPLY = (
    "I can help with vehicle symptoms, maintenance, repairs, and service bookings. "
    "I can't help with that topic."
)
AUTOMOTIVE_FALLBACK_REPLY = (
    "I can help with vehicle symptoms, but I can't determine the cause of this issue "
    "right now. Automotive symptoms can have several causes. Please share when it "
    "happens, whether the RPM rises without acceleration, whether shifting is delayed "
    "or harsh, and whether any warning lights are on."
)
AMBIGUOUS_REPLY = (
    "I found more than one possible vehicle issue. Could you provide more specific "
    "details about when the symptom happens and what you notice?"
)


@dataclass(frozen=True)
class ChatServiceResult:
    data: dict[str, Any]
    created: bool


class ChatService:
    """Coordinate conversation persistence and deterministic diagnosis."""

    def __init__(
        self,
        engine: DiagnosticEngine | None = None,
        gemini_service: GeminiService | None = None,
    ) -> None:
        self.engine = engine or DiagnosticEngine()
        self.gemini_service = gemini_service or GeminiService()

    @transaction.atomic
    def process_message(
        self,
        message: str,
        conversation_id: uuid.UUID | None = None,
    ) -> ChatServiceResult:
        conversation, created = self._get_or_create_conversation(conversation_id)
        context = self._build_context(conversation)

        Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content=message,
        )
        engine_result = self.engine.match(message, context)
        gemini_result, automotive_fallback = self._maybe_use_gemini(message, context, engine_result)
        response = (
            self._build_gemini_response(conversation, gemini_result)
            if gemini_result
            else self._build_automotive_fallback_response(conversation)
            if automotive_fallback
            else self._build_response(conversation, engine_result)
        )

        Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=response['reply'],
        )
        if gemini_result and gemini_result.status == MatchStatus.MATCHED:
            self._save_gemini_diagnosis(conversation, gemini_result, response)
        elif engine_result.status == MatchStatus.MATCHED and engine_result.matched_rule:
            self._save_diagnosis(conversation, engine_result, response)

        conversation.save(update_fields=['updated_at'])
        return ChatServiceResult(response, created)

    def _maybe_use_gemini(self, message, context, engine_result):
        if engine_result.status == MatchStatus.AMBIGUOUS:
            should_use = True
        elif engine_result.status == MatchStatus.UNSUPPORTED:
            should_use = self.gemini_service.should_handle_unsupported(message)
        else:
            should_use = False
        if not should_use:
            return None, False

        try:
            gemini_result = self.gemini_service.diagnose(message, context)
            if (
                engine_result.status == MatchStatus.AMBIGUOUS
                and gemini_result.status == MatchStatus.MATCHED.value
            ):
                return None, False
            return gemini_result, False
        except GeminiServiceError:
            return None, engine_result.status == MatchStatus.UNSUPPORTED and should_use

    def _get_or_create_conversation(
        self,
        conversation_id: uuid.UUID | None,
    ) -> tuple[Conversation, bool]:
        if conversation_id is not None:
            return Conversation.objects.get(pk=conversation_id), False
        return Conversation.objects.create(session_id=str(uuid.uuid4())), True

    def _build_context(self, conversation: Conversation) -> dict[str, Any]:
        user_messages = list(
            conversation.messages.filter(role=Message.Role.USER)
            .order_by('created_at')
            .values_list('content', flat=True)
        )
        if not user_messages:
            return {}

        context: dict[str, Any] = {
            'previous_messages': [],
            'follow_up_answers': {},
        }
        for user_message in user_messages:
            result = self.engine.match(user_message, context)
            context['previous_messages'] = [*context['previous_messages'], user_message][-6:]
            if result.matched_rule:
                context['matched_rule'] = result.matched_rule.rule_id
            if result.matched_rule and result.missing_information:
                key = result.missing_information[0]
                context['pending_follow_up'] = {
                    'rule_id': result.matched_rule.rule_id,
                    'key': key,
                }
            else:
                context.pop('pending_follow_up', None)
        return context

    def _build_response(self, conversation: Conversation, engine_result: Any) -> dict[str, Any]:
        status = engine_result.status
        diagnosis = None
        recommended_service = None
        if status == MatchStatus.UNSUPPORTED:
            reply = UNSUPPORTED_REPLY
        elif status == MatchStatus.AMBIGUOUS:
            reply = AMBIGUOUS_REPLY
        elif status == MatchStatus.NEEDS_INFORMATION:
            reply = engine_result.next_follow_up_question or (
                'Could you provide more information about the vehicle symptom?'
            )
        else:
            diagnosis = '; '.join(engine_result.possible_diagnoses)
            recommended_service = engine_result.recommended_service
            reply = f'Based on the information provided, possible issue(s): {diagnosis}.'

        return {
            'conversation_id': str(conversation.id),
            'status': status.value,
            'reply': reply,
            'diagnosis': diagnosis,
            'possible_diagnoses': list(engine_result.possible_diagnoses),
            'recommended_service': recommended_service,
            'safety_guidance': engine_result.safety_guidance,
            'matched_rule': engine_result.matched_rule.rule_id if engine_result.matched_rule else None,
            'matched_rules': [
                {
                    'rule_id': match.rule.rule_id,
                    'score': match.score,
                    'matched_groups': list(match.matched_groups),
                }
                for match in engine_result.matched_rules
            ],
            'missing_information': list(engine_result.missing_information),
            'next_follow_up_question': engine_result.next_follow_up_question,
        }

    def _build_automotive_fallback_response(self, conversation: Conversation) -> dict[str, Any]:
        return {
            'conversation_id': str(conversation.id),
            'status': MatchStatus.NEEDS_INFORMATION.value,
            'reply': AUTOMOTIVE_FALLBACK_REPLY,
            'diagnosis': None,
            'possible_diagnoses': [],
            'recommended_service': None,
            'safety_guidance': None,
            'matched_rule': None,
            'matched_rules': [],
            'missing_information': ['symptom_timing', 'shifting_behavior', 'warning_lights'],
            'next_follow_up_question': (
                'When does it happen, does the RPM rise without acceleration, and are any warning lights on?'
            ),
        }

    def _build_gemini_response(
        self,
        conversation: Conversation,
        gemini_result: GeminiDiagnosticResult,
    ) -> dict[str, Any]:
        diagnosis = (
            '; '.join(gemini_result.possible_diagnoses)
            if gemini_result.status == MatchStatus.MATCHED.value
            else None
        )
        return {
            'conversation_id': str(conversation.id),
            'status': gemini_result.status,
            'reply': gemini_result.reply,
            'diagnosis': diagnosis,
            'possible_diagnoses': list(gemini_result.possible_diagnoses),
            'recommended_service': gemini_result.recommended_service,
            'safety_guidance': gemini_result.safety_guidance,
            'matched_rule': None,
            'matched_rules': [],
            'missing_information': (
                ['additional_information']
                if gemini_result.status == MatchStatus.NEEDS_INFORMATION.value
                else []
            ),
            'next_follow_up_question': gemini_result.follow_up_question,
        }

    def _save_diagnosis(self, conversation: Conversation, engine_result: Any, response: dict[str, Any]) -> None:
        rule = engine_result.matched_rule
        previous_user_messages = list(
            conversation.messages.filter(role=Message.Role.USER).values_list('content', flat=True)
        )
        diagnosis_data = {
            'symptoms': list(engine_result.collected_symptoms),
            'follow_up_answers': self._collect_follow_up_answers(rule, previous_user_messages),
            'result': json.dumps(response, sort_keys=True),
            'recommended_service': engine_result.recommended_service or '',
            'source': Diagnosis.Source.RULE,
        }
        diagnosis = conversation.diagnoses.order_by('-created_at').first()
        if diagnosis is None:
            Diagnosis.objects.create(conversation=conversation, **diagnosis_data)
        else:
            for field, value in diagnosis_data.items():
                setattr(diagnosis, field, value)
            diagnosis.save(update_fields=[*diagnosis_data, 'created_at'])

    def _save_gemini_diagnosis(
        self,
        conversation: Conversation,
        gemini_result: GeminiDiagnosticResult,
        response: dict[str, Any],
    ) -> None:
        diagnosis_data = {
            'symptoms': ['gemini_fallback'],
            'follow_up_answers': {},
            'result': json.dumps(response, sort_keys=True),
            'recommended_service': gemini_result.recommended_service or '',
            'source': Diagnosis.Source.GEMINI,
        }
        diagnosis = conversation.diagnoses.order_by('-created_at').first()
        if diagnosis is None:
            Diagnosis.objects.create(conversation=conversation, **diagnosis_data)
        else:
            for field, value in diagnosis_data.items():
                setattr(diagnosis, field, value)
            diagnosis.save(update_fields=[*diagnosis_data, 'created_at'])

    def _collect_follow_up_answers(
        self,
        rule: DiagnosticRule,
        messages: list[str],
    ) -> dict[str, str]:
        text = normalize_text(' '.join(messages))
        answers = {}
        for key in rule.required_information:
            signal = next(
                (candidate for candidate in rule.information_signals[key] if candidate in text),
                'provided in conversation',
            )
            answers[key] = signal
        return answers