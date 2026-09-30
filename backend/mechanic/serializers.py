import re

from rest_framework import serializers
from rest_framework.exceptions import NotFound

from .models import Booking, Conversation, Diagnosis


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
    assistant_response = ChatResponseSerializer()


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


class BookingRequestSerializer(serializers.Serializer):
    diagnosis_id = serializers.IntegerField(required=True)
    conversation_id = serializers.UUIDField(required=True)
    customer_name = serializers.CharField(
        required=True,
        max_length=255,
        trim_whitespace=True,
    )
    phone = serializers.CharField(
        required=True,
        max_length=50,
        trim_whitespace=True,
    )
    email = serializers.EmailField(required=False, allow_blank=True)
    vehicle_make = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    vehicle_model = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    vehicle_year = serializers.IntegerField(required=False, allow_null=True)
    preferred_date = serializers.DateField(required=True)
    preferred_time = serializers.TimeField(required=True)
    service_address = serializers.CharField(required=True, trim_whitespace=True)

    def validate_phone(self, value):
        if (
            not re.fullmatch(r'[0-9+().\-\s]{7,50}', value)
            or sum(character.isdigit() for character in value) < 7
        ):
            raise serializers.ValidationError('Enter a valid phone number.')
        return value

    def validate_vehicle_year(self, value):
        if value is None:
            return value
        if value < 1886 or value > 2100:
            raise serializers.ValidationError('Enter a valid vehicle year.')
        return value

    def validate(self, attrs):
        try:
            diagnosis = Diagnosis.objects.select_related('conversation').get(
                pk=attrs['diagnosis_id']
            )
        except Diagnosis.DoesNotExist as exc:
            raise serializers.ValidationError(
                {'diagnosis_id': 'Diagnosis not found.'}
            ) from exc

        if diagnosis.conversation_id != attrs['conversation_id']:
            raise serializers.ValidationError(
                {'conversation_id': 'Conversation does not match the diagnosis.'}
            )

        attrs['_diagnosis'] = diagnosis
        return attrs


class BookingResponseSerializer(serializers.ModelSerializer):
    diagnosis_id = serializers.IntegerField(read_only=True)
    conversation_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Booking
        fields = (
            'id',
            'diagnosis_id',
            'conversation_id',
            'customer_name',
            'phone',
            'email',
            'vehicle_make',
            'vehicle_model',
            'vehicle_year',
            'preferred_date',
            'preferred_time',
            'service_address',
            'status',
            'created_at',
        )