import json
import shutil
import tempfile
import uuid
from unittest.mock import MagicMock, patch

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.functional import empty
from rest_framework.test import APIClient

from .models import Booking, Conversation, Diagnosis, MediaAttachment, Message
from .services.chat_service import ChatService
from .services.gemini_service import GeminiDiagnosticResult, GeminiService, GeminiServiceError


class ChatAPITests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.url = '/api/chat/'

	def post_message(self, message, conversation_id=None):
		payload = {'message': message}
		if conversation_id is not None:
			payload['conversation_id'] = str(conversation_id)
		return self.client.post(self.url, payload, format='json')

	def test_new_conversation_and_automotive_message(self):
		response = self.post_message("My car won't start")

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.data['status'], 'needs_information')
		self.assertEqual(response.data['matched_rule'], 'no_start')
		conversation = Conversation.objects.get(pk=response.data['conversation_id'])
		self.assertEqual(conversation.messages.count(), 2)

	def test_existing_conversation_continuation_uses_context(self):
		first_response = self.post_message("My car won't start")
		conversation_id = first_response.data['conversation_id']

		response = self.post_message("No, it doesn't crank", conversation_id)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['conversation_id'], conversation_id)
		self.assertEqual(response.data['matched_rule'], 'no_start')
		self.assertEqual(Conversation.objects.get(pk=conversation_id).messages.count(), 4)

	def test_follow_up_question_flow(self):
		response = self.post_message("My car won't start")

		self.assertEqual(response.data['status'], 'needs_information')
		self.assertEqual(
			response.data['reply'],
			'Does the engine crank or turn over when you try to start it?',
		)
		self.assertIsNone(response.data['diagnosis'])

	def test_diagnosis_after_sufficient_information(self):
		response = self.post_message(
			'My car will not start, it does not crank, the dashboard lights are on, '
			'there is no clicking, and I have a weak battery.'
		)

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.data['status'], 'matched')
		self.assertIsNotNone(response.data['diagnosis'])
		self.assertIsNotNone(response.data['recommended_service'])

	def test_unsupported_query(self):
		response = self.post_message('What is the weather today?')

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.data['status'], 'unsupported')
		self.assertIsNone(response.data['matched_rule'])
		self.assertIn('I can help with vehicle symptoms', response.data['reply'])

	def test_ambiguous_query(self):
		response = self.post_message('The steering wheel vibrates while braking')

		self.assertEqual(response.data['status'], 'ambiguous')
		self.assertGreaterEqual(len(response.data['matched_rules']), 2)
		self.assertIsNone(response.data['diagnosis'])
		self.assertIn('more than one', response.data['reply'])

	def test_empty_message_validation(self):
		response = self.client.post(self.url, {'message': '   '}, format='json')

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
		self.assertIn('message', response.data['error']['fields'])

	def test_invalid_conversation_id(self):
		response = self.post_message('My car will not start', uuid.uuid4())

		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.data['error']['code'], 'CONVERSATION_NOT_FOUND')

	def test_diagnosis_persistence(self):
		response = self.post_message(
			'My car will not start, it does not crank, the dashboard lights are on, '
			'there is no clicking, and I have a weak battery.'
		)

		diagnosis = Diagnosis.objects.get(conversation_id=response.data['conversation_id'])
		self.assertEqual(diagnosis.source, Diagnosis.Source.RULE)
		self.assertTrue(diagnosis.symptoms)
		self.assertTrue(diagnosis.follow_up_answers)
		self.assertEqual(diagnosis.recommended_service, response.data['recommended_service'])

	def test_assistant_message_persistence(self):
		response = self.post_message('What is the weather today?')

		messages = Message.objects.filter(conversation_id=response.data['conversation_id'])
		assistant_message = messages.get(role=Message.Role.ASSISTANT)
		self.assertEqual(assistant_message.content, response.data['reply'])


class MediaUploadAPITests(TestCase):
	def setUp(self):
		self.media_root = tempfile.mkdtemp()
		self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
		self.settings_override.enable()
		default_storage._wrapped = empty
		self.client = APIClient()
		self.url = '/api/upload/'
		self.conversation = Conversation.objects.create(session_id=str(uuid.uuid4()))

	def tearDown(self):
		default_storage._wrapped = empty
		self.settings_override.disable()
		shutil.rmtree(self.media_root, ignore_errors=True)

	def upload(self, name, content, content_type, conversation_id=None):
		return self.client.post(
			self.url,
			{
				'conversation_id': str(conversation_id or self.conversation.id),
				'file': SimpleUploadedFile(name, content, content_type=content_type),
			},
			format='multipart',
		)

	def test_valid_image_upload_creates_image_message_and_attachment(self):
		response = self.upload('inspection.jpg', b'\xff\xd8\xff\xe0image', 'image/jpeg')

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.data['attachment']['file_type'], 'image')
		self.assertTrue(response.data['attachment']['url'].startswith('/media/'))
		message = self.conversation.messages.get()
		attachment = self.conversation.media_attachments.get()
		self.assertEqual(message.message_type, Message.MessageType.IMAGE)
		self.assertEqual(attachment.message_id, message.id)
		self.assertTrue(default_storage.exists(attachment.file.name))

	def test_valid_audio_upload(self):
		response = self.upload('engine.mp3', b'ID3\x04\x00audio', 'audio/mpeg')

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.data['attachment']['file_type'], 'audio')
		self.assertEqual(self.conversation.messages.get().message_type, Message.MessageType.AUDIO)

	def test_valid_video_upload(self):
		response = self.upload('walkaround.mp4', b'\x00\x00\x00\x18ftypisom', 'video/mp4')

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.data['attachment']['file_type'], 'video')
		self.assertEqual(self.conversation.messages.get().message_type, Message.MessageType.VIDEO)

	def test_missing_file(self):
		response = self.client.post(
			self.url,
			{'conversation_id': str(self.conversation.id)},
			format='multipart',
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
		self.assertIn('file', response.data['error']['fields'])

	def test_invalid_conversation_id(self):
		response = self.upload('inspection.jpg', b'\xff\xd8\xff\xe0image', 'image/jpeg', uuid.uuid4())

		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.data['error']['code'], 'CONVERSATION_NOT_FOUND')

	def test_unsupported_file_type(self):
		response = self.upload('notes.txt', b'plain text', 'text/plain')

		self.assertEqual(response.status_code, 415)
		self.assertEqual(response.data['error']['code'], 'UNSUPPORTED_MEDIA_TYPE')

	def test_oversized_file(self):
		with self.settings(MAX_UPLOAD_SIZE_BYTES=4):
			response = self.upload('large.jpg', b'\xff\xd8\xff\xe0large', 'image/jpeg')

		self.assertEqual(response.status_code, 413)
		self.assertEqual(response.data['error']['code'], 'FILE_TOO_LARGE')

	def test_response_metadata_and_database_records(self):
		content = b'\x89PNG\r\n\x1a\nimage-data'
		response = self.upload('inspection.png', content, 'image/png')

		self.assertEqual(response.data['conversation_id'], str(self.conversation.id))
		self.assertEqual(response.data['message_id'], self.conversation.messages.get().id)
		self.assertEqual(response.data['attachment']['file_size'], len(content))
		self.assertTrue(response.data['attachment']['filename'].endswith('.png'))
		self.assertEqual(MediaAttachment.objects.count(), 1)
		self.assertEqual(Message.objects.count(), 1)


class GeminiFallbackTests(TestCase):
	def setUp(self):
		self.conversation = Conversation.objects.create(session_id=str(uuid.uuid4()))

	def make_gemini(self, result=None, error=None, automotive=False):
		gemini = MagicMock()
		gemini.should_handle_unsupported.return_value = automotive
		if error:
			gemini.diagnose.side_effect = error
		else:
			gemini.diagnose.return_value = result
		return gemini

	def test_rule_based_query_does_not_call_gemini(self):
		gemini = self.make_gemini()
		result = ChatService(gemini_service=gemini).process_message(
			"My car won't start",
			self.conversation.id,
		)

		self.assertEqual(result.data['status'], 'needs_information')
		gemini.diagnose.assert_not_called()

	def test_unsupported_non_automotive_query_does_not_call_gemini(self):
		gemini = self.make_gemini()
		result = ChatService(gemini_service=gemini).process_message(
			'What is the weather today?',
			self.conversation.id,
		)

		self.assertEqual(result.data['status'], 'unsupported')
		gemini.should_handle_unsupported.assert_called_once()
		gemini.diagnose.assert_not_called()

	def test_automotive_unsupported_query_uses_gemini_fallback(self):
		gemini_result = GeminiDiagnosticResult(
			'matched',
			'The transmission may have a slipping clutch or low fluid.',
			('Transmission or clutch problem',),
			'Transmission inspection and fluid check',
			'Avoid continued driving if the vehicle cannot select gears safely.',
			None,
		)
		gemini = self.make_gemini(gemini_result, automotive=True)
		result = ChatService(gemini_service=gemini).process_message(
			'My transmission is slipping',
			self.conversation.id,
		)

		self.assertEqual(result.data['status'], 'matched')
		self.assertEqual(result.data['diagnosis'], 'Transmission or clutch problem')
		self.assertEqual(result.data['recommended_service'], 'Transmission inspection and fluid check')
		gemini.diagnose.assert_called_once()
		self.assertEqual(self.conversation.diagnoses.get().source, Diagnosis.Source.GEMINI)

	def test_mocked_structured_gemini_response_is_converted(self):
		client = MagicMock()
		client.models.generate_content.return_value.text = json.dumps({
			'status': 'matched',
			'reply': 'The transmission may have a slipping clutch.',
			'possible_diagnoses': ['Transmission or clutch problem'],
			'recommended_service': 'Transmission inspection',
			'safety_guidance': 'Avoid driving if gear engagement is unsafe.',
			'follow_up_question': None,
		})
		with self.settings(GEMINI_API_KEY='test-key'):
			result = ChatService(gemini_service=GeminiService(client=client)).process_message(
				'My transmission is slipping',
				self.conversation.id,
			)

		self.assertEqual(result.data['status'], 'matched')
		self.assertEqual(result.data['diagnosis'], 'Transmission or clutch problem')
		self.assertEqual(result.data['recommended_service'], 'Transmission inspection')
		client.models.generate_content.assert_called_once()

	def test_ambiguous_automotive_query_uses_gemini(self):
		gemini_result = GeminiDiagnosticResult(
			'needs_information',
			'Is the vibration present only during braking or also at highway speed?',
			(),
			None,
			'If braking is affected, avoid driving until inspected.',
			'When does the vibration occur?',
		)
		gemini = self.make_gemini(gemini_result)
		result = ChatService(gemini_service=gemini).process_message(
			'The steering wheel vibrates while braking',
			self.conversation.id,
		)

		self.assertEqual(result.data['status'], 'needs_information')
		self.assertEqual(result.data['next_follow_up_question'], 'When does the vibration occur?')
		gemini.diagnose.assert_called_once()

	@patch('mechanic.services.chat_service.GeminiService')
	def test_ambiguous_gemini_match_does_not_create_definitive_diagnosis(self, gemini_class):
		gemini = gemini_class.return_value
		gemini.diagnose.return_value = GeminiDiagnosticResult(
			'matched',
			'Possible warped rotor.',
			('Warped brake rotor',),
			'Brake inspection',
			'Avoid driving if braking is reduced.',
			None,
		)

		response = APIClient().post(
			'/api/chat/',
			{'message': 'The steering wheel vibrates while braking'},
			format='json',
		)

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.data['status'], 'ambiguous')
		self.assertIsNone(response.data['diagnosis'])
		self.assertGreaterEqual(len(response.data['matched_rules']), 2)
		self.assertEqual(Diagnosis.objects.count(), 0)
		gemini.diagnose.assert_called_once()

	def test_gemini_failure_falls_back_to_deterministic_response(self):
		gemini = self.make_gemini(error=GeminiServiceError('provider unavailable'), automotive=True)
		result = ChatService(gemini_service=gemini).process_message(
			'My transmission is slipping',
			self.conversation.id,
		)

		self.assertEqual(result.data['status'], 'unsupported')
		self.assertIn('vehicle symptoms', result.data['reply'])

	def test_missing_gemini_configuration_is_graceful(self):
		with self.settings(GEMINI_API_KEY=''):
			result = ChatService(gemini_service=GeminiService()).process_message(
				'My transmission is slipping',
				self.conversation.id,
			)

		self.assertEqual(result.data['status'], 'unsupported')
		self.assertIn('vehicle symptoms', result.data['reply'])


class DiagnosisAPITests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.url = '/api/diagnosis/'

	def diagnose(self, conversation_id):
		return self.client.post(self.url, {'conversation_id': str(conversation_id)}, format='json')

	def test_missing_conversation_id(self):
		response = self.client.post(self.url, {}, format='json')

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')

	def test_nonexistent_conversation(self):
		response = self.diagnose(uuid.uuid4())

		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.data['error']['code'], 'CONVERSATION_NOT_FOUND')

	def test_needs_information_does_not_create_diagnosis(self):
		chat_response = self.client.post('/api/chat/', {'message': "My car won't start"}, format='json')

		response = self.diagnose(chat_response.data['conversation_id'])

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['status'], 'needs_information')
		self.assertIsNone(response.data['diagnosis_id'])
		self.assertEqual(Diagnosis.objects.count(), 0)

	def test_ambiguous_does_not_create_diagnosis(self):
		chat_response = self.client.post(
			'/api/chat/',
			{'message': 'The steering wheel vibrates while braking'},
			format='json',
		)

		response = self.diagnose(chat_response.data['conversation_id'])

		self.assertEqual(response.data['status'], 'ambiguous')
		self.assertIsNone(response.data['diagnosis_id'])
		self.assertEqual(Diagnosis.objects.count(), 0)

	def test_unsupported_does_not_create_diagnosis(self):
		chat_response = self.client.post('/api/chat/', {'message': 'What is the weather today?'}, format='json')

		response = self.diagnose(chat_response.data['conversation_id'])

		self.assertEqual(response.data['status'], 'unsupported')
		self.assertIsNone(response.data['diagnosis_id'])
		self.assertEqual(Diagnosis.objects.count(), 0)

	def test_final_rule_diagnosis_is_created_and_reused(self):
		chat_response = self.client.post(
			'/api/chat/',
			{
				'message': 'My car will not start, it does not crank, the dashboard lights are on, '
				' there is no clicking, and I have a weak battery.',
			},
			format='json',
		)
		conversation_id = chat_response.data['conversation_id']

		first_response = self.diagnose(conversation_id)
		second_response = self.diagnose(conversation_id)

		self.assertEqual(first_response.status_code, 200)
		self.assertEqual(first_response.data['status'], 'matched')
		self.assertEqual(first_response.data['source'], Diagnosis.Source.RULE)
		self.assertEqual(first_response.data['diagnosis_id'], second_response.data['diagnosis_id'])
		self.assertEqual(Diagnosis.objects.count(), 1)

	def test_existing_gemini_diagnosis_preserves_source(self):
		conversation = Conversation.objects.create(session_id=str(uuid.uuid4()))
		diagnosis = Diagnosis.objects.create(
			conversation=conversation,
			symptoms=['gemini_fallback'],
			result=json.dumps({
				'status': 'matched',
				'diagnosis': 'Transmission or clutch problem',
				'recommended_service': 'Transmission inspection',
				'safety_guidance': 'Avoid driving if gear engagement is unsafe.',
			}),
			recommended_service='Transmission inspection',
			source=Diagnosis.Source.GEMINI,
		)

		response = self.diagnose(conversation.id)

		self.assertEqual(response.data['diagnosis_id'], diagnosis.id)
		self.assertEqual(response.data['source'], Diagnosis.Source.GEMINI)
		self.assertEqual(response.data['diagnosis'], 'Transmission or clutch problem')


class BookingAPITests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.conversation = Conversation.objects.create(session_id=str(uuid.uuid4()))
		self.diagnosis = Diagnosis.objects.create(
			conversation=self.conversation,
			symptoms=['starting problem'],
			result=json.dumps({'diagnosis': 'Weak or discharged battery'}),
			recommended_service='Battery and starting-system inspection',
			source=Diagnosis.Source.RULE,
		)

	def payload(self, **overrides):
		data = {
			'diagnosis_id': self.diagnosis.id,
			'conversation_id': str(self.conversation.id),
			'customer_name': 'Avery Morgan',
			'phone': '+1 555 123 4567',
			'email': 'avery@example.com',
			'vehicle_make': 'Toyota',
			'vehicle_model': 'Corolla',
			'vehicle_year': 2020,
			'preferred_date': '2026-10-05',
			'preferred_time': '10:30:00',
			'service_address': '12 Main Street',
		}
		data.update(overrides)
		return data

	def test_valid_booking_creation_and_retrieval(self):
		response = self.client.post('/api/booking/', self.payload(), format='json')

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.data['status'], Booking.Status.PENDING)
		self.assertEqual(response.data['diagnosis_id'], self.diagnosis.id)
		self.assertEqual(response.data['conversation_id'], str(self.conversation.id))

		detail = self.client.get(f"/api/booking/{response.data['id']}/")
		self.assertEqual(detail.status_code, 200)
		self.assertEqual(detail.data['id'], response.data['id'])
		self.assertEqual(detail.data['customer_name'], 'Avery Morgan')

	def test_missing_required_fields(self):
		response = self.client.post('/api/booking/', {'diagnosis_id': self.diagnosis.id}, format='json')

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
		self.assertIn('customer_name', response.data['error']['fields'])

	def test_invalid_field_values(self):
		response = self.client.post(
			'/api/booking/',
			self.payload(phone='bad', email='bad', preferred_date='not-a-date'),
			format='json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn('phone', response.data['error']['fields'])
		self.assertIn('email', response.data['error']['fields'])
		self.assertIn('preferred_date', response.data['error']['fields'])

	def test_diagnosis_and_conversation_must_match(self):
		other_conversation = Conversation.objects.create(session_id=str(uuid.uuid4()))

		response = self.client.post(
			'/api/booking/',
			self.payload(conversation_id=str(other_conversation.id)),
			format='json',
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn('conversation_id', response.data['error']['fields'])

	def test_missing_booking_returns_not_found(self):
		response = self.client.get('/api/booking/999999/')

		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.data['error']['code'], 'BOOKING_NOT_FOUND')
