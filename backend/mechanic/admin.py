from django.contrib import admin

from .models import Booking, Conversation, Diagnosis, MediaAttachment, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
	list_display = ('id', 'session_id', 'created_at', 'updated_at')
	search_fields = ('id', 'session_id')
	readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
	list_display = ('conversation', 'role', 'message_type', 'created_at')
	list_filter = ('role', 'message_type', 'created_at')
	search_fields = ('conversation__id', 'content')
	readonly_fields = ('created_at',)


@admin.register(MediaAttachment)
class MediaAttachmentAdmin(admin.ModelAdmin):
	list_display = ('conversation', 'message', 'file_type', 'file_size', 'created_at')
	list_filter = ('file_type', 'created_at')
	search_fields = ('conversation__id', 'file_type')
	readonly_fields = ('created_at',)


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
	list_display = ('conversation', 'source', 'recommended_service', 'created_at')
	list_filter = ('source', 'created_at')
	search_fields = ('conversation__id', 'result', 'recommended_service')
	readonly_fields = ('created_at',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
	list_display = (
		'customer_name',
		'phone',
		'vehicle_make',
		'vehicle_model',
		'preferred_date',
		'preferred_time',
		'status',
		'created_at',
	)
	list_filter = ('status', 'preferred_date', 'created_at')
	search_fields = (
		'customer_name',
		'phone',
		'email',
		'vehicle_make',
		'vehicle_model',
	)
	readonly_fields = ('created_at',)
