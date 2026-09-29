"""Small, validated adapter for selective Gemini diagnostic fallback."""

import json
from dataclasses import dataclass
from typing import Any

from django.conf import settings


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


class GeminiService:
    """Call Gemini only for explicitly selected automotive fallback cases."""

    _AUTOMOTIVE_TERMS = (
        'car', 'vehicle', 'truck', 'engine', 'motor', 'brake', 'tire', 'tyre',
        'wheel', 'steering', 'battery', 'oil', 'coolant', 'radiator', 'transmission',
        'gearbox', 'gear shifting', 'shifting', 'slipping', 'drivetrain', 'differential',
        'suspension', 'gear', 'clutch', 'exhaust', 'catalytic converter', 'engine light',
        'dashboard', 'hood', 'bonnet', 'ac', 'air conditioning', 'alternator',
        'starter motor', 'starter', 'spark plug', 'fuel pump', 'fuel', 'wheel alignment',
    )

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(getattr(settings, 'GEMINI_API_KEY', ''))

    def should_handle_unsupported(self, message: str) -> bool:
        """Limit fallback for engine-unsupported messages to likely vehicle queries."""
        normalized = message.lower()
        return any(term in normalized for term in self._AUTOMOTIVE_TERMS)

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

        return GeminiDiagnosticResult(
            status=status,
            reply=reply.strip(),
            possible_diagnoses=tuple(item.strip() for item in diagnoses),
            recommended_service=self._optional_text(payload.get('recommended_service')),
            safety_guidance=self._optional_text(payload.get('safety_guidance')),
            follow_up_question=self._optional_text(payload.get('follow_up_question')),
        )

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise GeminiServiceError('Gemini returned an invalid text field.')
        return value.strip() or None