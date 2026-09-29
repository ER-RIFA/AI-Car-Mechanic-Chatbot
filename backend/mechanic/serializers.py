from rest_framework import serializers
from rest_framework.exceptions import NotFound

from .models import Conversation


class ChatRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    message = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError('Message cannot be empty.')
        return value.strip()

    def validate_conversation_id(self, value):
        if value is not None and not Conversation.objects.filter(pk=value).exists():
            raise NotFound('Conversation not found.')
        return value


class ChatResponseSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    status = serializers.CharField()
    reply = serializers.CharField()
    diagnosis = serializers.CharField(allow_null=True)
    possible_diagnoses = serializers.ListField(child=serializers.CharField())
    recommended_service = serializers.CharField(allow_null=True)
    safety_guidance = serializers.CharField(allow_null=True)
    matched_rule = serializers.CharField(allow_null=True)
    matched_rules = serializers.ListField(child=serializers.DictField())
    missing_information = serializers.ListField(child=serializers.CharField())
    next_follow_up_question = serializers.CharField(allow_null=True)


class UploadRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=True)
    file = serializers.FileField(required=True, allow_empty_file=False)

    def validate_conversation_id(self, value):
        if not Conversation.objects.filter(pk=value).exists():
            raise NotFound('Conversation not found.')
        return value


class AttachmentMetadataSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    file_type = serializers.CharField()
    file_size = serializers.IntegerField()
    url = serializers.CharField()
    filename = serializers.CharField()


class UploadResponseSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    message_id = serializers.IntegerField()
    attachment = AttachmentMetadataSerializer()


class DiagnosisRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=True)

    def validate_conversation_id(self, value):
        if not Conversation.objects.filter(pk=value).exists():
            raise NotFound('Conversation not found.')
        return value


class DiagnosisResponseSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    diagnosis_id = serializers.IntegerField(allow_null=True)
    status = serializers.CharField()
    diagnosis = serializers.CharField(allow_null=True)
    result = serializers.JSONField(allow_null=True)
    recommended_service = serializers.CharField(allow_null=True)
    safety_guidance = serializers.CharField(allow_null=True)
    source = serializers.CharField(allow_null=True)
    message = serializers.CharField(allow_null=True)