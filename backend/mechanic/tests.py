import uuid

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Conversation, Diagnosis, Message


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
