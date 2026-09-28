import uuid

from django.db import models


class Conversation(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	session_id = models.CharField(max_length=100, db_index=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-updated_at']

	def __str__(self):
		return f'Conversation {self.id}'


class Message(models.Model):
	class Role(models.TextChoices):
		USER = 'user', 'User'
		ASSISTANT = 'assistant', 'Assistant'
		SYSTEM = 'system', 'System'

	class MessageType(models.TextChoices):
		TEXT = 'text', 'Text'
		IMAGE = 'image', 'Image'
		AUDIO = 'audio', 'Audio'
		VIDEO = 'video', 'Video'

	conversation = models.ForeignKey(
		Conversation,
		on_delete=models.CASCADE,
		related_name='messages',
	)
	role = models.CharField(max_length=20, choices=Role.choices)
	content = models.TextField(blank=True, default='')
	message_type = models.CharField(
		max_length=10,
		choices=MessageType.choices,
		default=MessageType.TEXT,
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at']
		indexes = [
			models.Index(fields=['conversation', 'created_at']),
		]

	def __str__(self):
		return f'{self.get_role_display()} message in {self.conversation_id}'


class MediaAttachment(models.Model):
	conversation = models.ForeignKey(
		Conversation,
		on_delete=models.CASCADE,
		related_name='media_attachments',
	)
	message = models.ForeignKey(
		Message,
		on_delete=models.CASCADE,
		related_name='media_attachments',
	)
	file = models.FileField(upload_to='chat_media/%Y/%m/%d/')
	file_type = models.CharField(max_length=100)
	file_size = models.PositiveBigIntegerField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.file_type} attachment for {self.conversation_id}'


class Diagnosis(models.Model):
	class Source(models.TextChoices):
		RULE = 'rule', 'Rule engine'
		GEMINI = 'gemini', 'Gemini'
		HYBRID = 'hybrid', 'Rule engine and Gemini'

	conversation = models.ForeignKey(
		Conversation,
		on_delete=models.CASCADE,
		related_name='diagnoses',
	)
	symptoms = models.JSONField(default=list)
	follow_up_answers = models.JSONField(default=dict)
	result = models.TextField()
	recommended_service = models.CharField(max_length=255, blank=True, default='')
	source = models.CharField(
		max_length=20,
		choices=Source.choices,
		default=Source.RULE,
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'Diagnosis for {self.conversation_id}'


class Booking(models.Model):
	class Status(models.TextChoices):
		PENDING = 'pending', 'Pending'
		CONFIRMED = 'confirmed', 'Confirmed'
		CANCELLED = 'cancelled', 'Cancelled'

	diagnosis = models.ForeignKey(
		Diagnosis,
		on_delete=models.PROTECT,
		related_name='bookings',
	)
	conversation = models.ForeignKey(
		Conversation,
		on_delete=models.PROTECT,
		related_name='bookings',
	)
	customer_name = models.CharField(max_length=255)
	phone = models.CharField(max_length=50)
	email = models.EmailField(blank=True, default='')
	vehicle_make = models.CharField(max_length=100, blank=True, default='')
	vehicle_model = models.CharField(max_length=100, blank=True, default='')
	vehicle_year = models.PositiveSmallIntegerField(null=True, blank=True)
	preferred_date = models.DateField()
	preferred_time = models.TimeField()
	service_address = models.TextField()
	status = models.CharField(
		max_length=20,
		choices=Status.choices,
		default=Status.PENDING,
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['status', 'preferred_date']),
		]

	def __str__(self):
		return f'Booking for {self.customer_name} on {self.preferred_date}'
