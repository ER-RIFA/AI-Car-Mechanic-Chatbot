import json
import uuid
from dataclasses import dataclass
from typing import Any

from mechanic.diagnostic_engine import DiagnosticEngine, MatchStatus

from ..models import Conversation, Diagnosis, Message
from .chat_service import ChatService


@dataclass(frozen=True)
class DiagnosisServiceResult:
	data: dict[str, Any]


class DiagnosisService:
	"""Return or finalize one diagnosis using the existing chat services."""

	def __init__(self, engine: DiagnosticEngine | None = None) -> None:
		self.chat_service = ChatService(engine=engine)

	def diagnose(self, conversation_id: uuid.UUID) -> DiagnosisServiceResult:
		conversation = Conversation.objects.get(pk=conversation_id)
		existing = conversation.diagnoses.first()
		if existing is not None:
			return DiagnosisServiceResult(self._serialize_existing(conversation, existing))

		user_messages = list(
			conversation.messages.filter(role=Message.Role.USER)
			.order_by('created_at')
			.values_list('content', flat=True)
		)
		if not user_messages:
			return DiagnosisServiceResult(
				self._not_ready(conversation, MatchStatus.UNSUPPORTED, 'No vehicle information has been provided yet.')
			)

		engine_result = self.chat_service.engine.match(' '.join(user_messages))
		if engine_result.status != MatchStatus.MATCHED:
			return DiagnosisServiceResult(self._not_ready(conversation, engine_result.status))

		response = self.chat_service._build_response(conversation, engine_result)
		self.chat_service._save_diagnosis(conversation, engine_result, response)
		diagnosis = conversation.diagnoses.first()
		return DiagnosisServiceResult(self._serialize_existing(conversation, diagnosis))

	def _serialize_existing(self, conversation: Conversation, diagnosis: Diagnosis) -> dict[str, Any]:
		try:
			result = json.loads(diagnosis.result)
		except (TypeError, json.JSONDecodeError):
			result = {'diagnosis': diagnosis.result}
		if not isinstance(result, dict):
			result = {'diagnosis': str(result)}

		diagnosis_text = result.get('diagnosis')
		if not diagnosis_text:
			diagnosis_text = '; '.join(result.get('possible_diagnoses', [])) or diagnosis.result
		return {
			'conversation_id': str(conversation.id),
			'diagnosis_id': diagnosis.id,
			'status': result.get('status', MatchStatus.MATCHED.value),
			'diagnosis': diagnosis_text,
			'result': result,
			'recommended_service': result.get('recommended_service') or diagnosis.recommended_service or None,
			'safety_guidance': result.get('safety_guidance'),
			'source': diagnosis.source,
			'message': None,
		}

	def _not_ready(
		self,
		conversation: Conversation,
		status: MatchStatus,
		message: str | None = None,
	) -> dict[str, Any]:
		messages = {
			MatchStatus.NEEDS_INFORMATION: 'More vehicle information is required before a diagnosis can be finalized.',
			MatchStatus.AMBIGUOUS: 'The conversation is ambiguous. Please provide more specific vehicle symptoms.',
			MatchStatus.UNSUPPORTED: 'The conversation does not contain a supported vehicle problem to diagnose.',
		}
		return {
			'conversation_id': str(conversation.id),
			'diagnosis_id': None,
			'status': status.value,
			'diagnosis': None,
			'result': None,
			'recommended_service': None,
			'safety_guidance': None,
			'source': None,
			'message': message or messages[status],
		}