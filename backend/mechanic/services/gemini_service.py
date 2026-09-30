"""Small, validated adapter for selective Gemini diagnostic fallback."""

import json
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from ..diagnostic_engine.normalizer import normalize_text
from ..diagnostic_engine.semantics import extract_semantics


class GeminiServiceError(Exception):
    """Expected configuration, provider, or response validation failure."""


@dataclass(frozen=True)
class GeminiDiagnosticResult:
    status: str
    reply: str
    possible_diagnoses: tuple[str, ...]
    recommended_service: str | None
    safety_guidance: str | None
    follow_up_question: str | None
    component: str | None = None
    complaint: str | None = None
    confidence: float | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None


@dataclass(frozen=True)
class GeminiFollowUpResult:
    answered: bool
    answer: str | None
    facts: dict[str, Any]
    confidence: float


class GeminiService:
    """Call Gemini only for explicitly selected automotive fallback cases."""

    _AUTOMOTIVE_CONTEXT_TERMS = {
        'car', 'vehicle', 'truck', 'automobile', 'driving', 'braking', 'accelerating',
        'turning', 'dashboard', 'hood', 'bonnet', 'under the car', 'roadside',
    }

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(getattr(settings, 'GEMINI_API_KEY', ''))

    def should_handle_unsupported(self, message: str) -> bool:
        """Limit fallback for engine-unsupported messages to likely vehicle queries."""
        normalized = normalize_text(message)
        evidence = extract_semantics(normalized)
        if evidence.components:
            return True
        return any(
            term in normalized.split() or term in normalized
            for term in self._AUTOMOTIVE_CONTEXT_TERMS
        )

    def diagnose(self, message: str, context: dict[str, Any] | None = None) -> GeminiDiagnosticResult:
        if not self.is_configured:
            raise GeminiServiceError('Gemini is not configured.')

        client = self._get_client()
        prompt = self._build_prompt(message, context or {})
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.2,
                },
            )
            return self._parse_response(response.text)
        except GeminiServiceError:
            raise
        except Exception as exc:
            raise GeminiServiceError('Gemini could not process the request.') from exc

    def interpret_follow_up(
        self,
        message: str,
        question: str,
        rule_id: str,
        field: str,
        context: dict[str, Any] | None = None,
    ) -> GeminiFollowUpResult:
        """Interpret one pending field; this endpoint cannot return a diagnosis."""
        if not self.is_configured:
            raise GeminiServiceError('Gemini is not configured.')
        client = self._get_client()
        prompt = json.dumps({
            'role': 'structured follow-up interpreter',
            'instruction': (
                'Interpret the user response only relative to the pending question. '
                'Do not diagnose, infer unseen observations, or answer a different topic.'
            ),
            'output_schema': {
                'answered': 'boolean',
                'answer': 'short semantic label or null',
                'facts': 'object of field facts or empty object',
                'confidence': 'number from 0 to 1',
            },
            'rule_id': rule_id,
            'field': field,
            'question': question,
            'message': message,
            'context': context or {},
        })
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config={'response_mime_type': 'application/json', 'temperature': 0.0},
            )
            return self._parse_follow_up_response(response.text)
        except GeminiServiceError:
            raise
        except Exception as exc:
            raise GeminiServiceError('Gemini could not interpret the follow-up.') from exc

    def analyze_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        context: dict[str, Any] | None = None,
    ) -> GeminiDiagnosticResult:
        """Analyze an uploaded automotive image when a later service explicitly requests it."""
        if not self.is_configured:
            raise GeminiServiceError('Gemini is not configured.')

        client = self._get_client()
        try:
            from google.genai import types

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    self._build_prompt('Interpret this uploaded automotive image.', context or {}),
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.2,
                },
            )
            return self._parse_response(response.text)
        except GeminiServiceError:
            raise
        except Exception as exc:
            raise GeminiServiceError('Gemini could not analyze the image.') from exc

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai

                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as exc:
                raise GeminiServiceError('Gemini client is unavailable.') from exc
        return self._client

    def _build_prompt(self, message: str, context: dict[str, Any]) -> str:
        return json.dumps({
            'role': 'senior automobile technician',
            'scope': 'vehicle symptoms, maintenance, repairs, and service guidance only',
            'instruction': (
                'Provide a possible diagnosis, not certainty. Ask one relevant follow-up '
                'question when information is insufficient. Include proportional safety guidance. '
                'Politely reject unrelated topics.'
            ),
            'output_schema': {
                'status': 'matched or needs_information',
                'reply': 'string',
                'component': 'semantic automotive component or null',
                'complaint': 'semantic complaint or null',
                'confidence': 'number from 0 to 1',
                'needs_clarification': 'boolean',
                'clarification_question': 'string or null',
                'possible_diagnoses': ['string'],
                'recommended_service': 'string or null',
                'safety_guidance': 'string or null',
                'follow_up_question': 'string or null',
            },
            'message': message,
            'context': context,
        })

    def _parse_response(self, raw_text: str) -> GeminiDiagnosticResult:
        try:
            payload = json.loads(raw_text.strip().removeprefix('```json').removesuffix('```').strip())
        except (json.JSONDecodeError, AttributeError) as exc:
            raise GeminiServiceError('Gemini returned invalid structured data.') from exc

        if not isinstance(payload, dict):
            raise GeminiServiceError('Gemini returned an invalid response object.')
        status = payload.get('status')
        reply = payload.get('reply')
        diagnoses = payload.get('possible_diagnoses', [])
        if status not in {'matched', 'needs_information'} or not isinstance(reply, str) or not reply.strip():
            raise GeminiServiceError('Gemini response is missing required fields.')
        if not isinstance(diagnoses, list) or not all(isinstance(item, str) and item.strip() for item in diagnoses):
            raise GeminiServiceError('Gemini diagnoses are not structured correctly.')

        confidence = payload.get('confidence')
        if confidence is not None and (not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
            raise GeminiServiceError('Gemini confidence is invalid.')
        needs_clarification = payload.get('needs_clarification', status == 'needs_information')
        if not isinstance(needs_clarification, bool):
            raise GeminiServiceError('Gemini clarification state is invalid.')

        return GeminiDiagnosticResult(
            status=status,
            reply=reply.strip(),
            possible_diagnoses=tuple(item.strip() for item in diagnoses),
            recommended_service=self._optional_text(payload.get('recommended_service')),
            safety_guidance=self._optional_text(payload.get('safety_guidance')),
            follow_up_question=self._optional_text(payload.get('follow_up_question')),
            component=self._optional_text(payload.get('component')),
            complaint=self._optional_text(payload.get('complaint')),
            confidence=float(confidence) if confidence is not None else None,
            needs_clarification=needs_clarification,
            clarification_question=self._optional_text(payload.get('clarification_question')),
        )

    def _parse_follow_up_response(self, raw_text: str) -> GeminiFollowUpResult:
        try:
            payload = json.loads(raw_text.strip().removeprefix('```json').removesuffix('```').strip())
        except (json.JSONDecodeError, AttributeError) as exc:
            raise GeminiServiceError('Gemini returned invalid follow-up data.') from exc
        if not isinstance(payload, dict) or not isinstance(payload.get('answered'), bool):
            raise GeminiServiceError('Gemini follow-up data is missing answered.')
        answer = payload.get('answer')
        facts = payload.get('facts', {})
        confidence = payload.get('confidence')
        if answer is not None and (not isinstance(answer, str) or not answer.strip()):
            raise GeminiServiceError('Gemini follow-up answer is invalid.')
        if not isinstance(facts, dict) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise GeminiServiceError('Gemini follow-up facts are invalid.')
        if payload['answered'] and answer is None:
            raise GeminiServiceError('Gemini answered follow-up without a semantic label.')
        return GeminiFollowUpResult(payload['answered'], answer.strip() if answer else None, facts, float(confidence))

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise GeminiServiceError('Gemini returned an invalid text field.')
        return value.strip() or None