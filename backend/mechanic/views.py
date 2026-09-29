from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking
from .serializers import (
	ChatRequestSerializer,
	ChatResponseSerializer,
	BookingRequestSerializer,
	BookingResponseSerializer,
	DiagnosisRequestSerializer,
	DiagnosisResponseSerializer,
	UploadRequestSerializer,
	UploadResponseSerializer,
)
from .services.chat_service import ChatService
from .services.booking_service import BookingService
from .services.diagnosis_service import DiagnosisService
from .services.media_service import MediaUploadError, MediaUploadService


def _error_response(code, message, fields=None, http_status=status.HTTP_400_BAD_REQUEST):
	error = {'code': code, 'message': message}
	if fields is not None:
		error['fields'] = fields
	return Response({'error': error}, status=http_status)


class ChatAPIView(APIView):
	def post(self, request):
		serializer = ChatRequestSerializer(data=request.data)
		try:
			serializer.is_valid(raise_exception=True)
		except NotFound as exc:
			return _error_response(
				'CONVERSATION_NOT_FOUND',
				str(exc.detail),
				http_status=status.HTTP_404_NOT_FOUND,
			)
		except Exception:
			if serializer.errors:
				fields = {
					field: [str(error) for error in errors]
					for field, errors in serializer.errors.items()
				}
				message = next(iter(fields.values()))[0]
				return _error_response('VALIDATION_ERROR', message, fields)
			raise

		try:
			result = ChatService().process_message(**serializer.validated_data)
		except NotFound:
			return _error_response(
				'CONVERSATION_NOT_FOUND',
				'Conversation not found.',
				http_status=status.HTTP_404_NOT_FOUND,
			)
		except Exception:
			return _error_response(
				'INTERNAL_ERROR',
				'An unexpected error occurred while processing the message.',
				http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)

		response_serializer = ChatResponseSerializer(result.data)
		response_status = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
		return Response(response_serializer.data, status=response_status)


class DiagnosisAPIView(APIView):
	def post(self, request):
		serializer = DiagnosisRequestSerializer(data=request.data)
		try:
			serializer.is_valid(raise_exception=True)
		except NotFound as exc:
			return _error_response(
				'CONVERSATION_NOT_FOUND',
				str(exc.detail),
				http_status=status.HTTP_404_NOT_FOUND,
			)
		except Exception:
			if serializer.errors:
				fields = {
					field: [str(error) for error in errors]
					for field, errors in serializer.errors.items()
				}
				message = next(iter(fields.values()))[0]
				return _error_response('VALIDATION_ERROR', message, fields)
			raise

		result = DiagnosisService().diagnose(serializer.validated_data['conversation_id'])
		return Response(DiagnosisResponseSerializer(result.data).data)


class BookingAPIView(APIView):
	def post(self, request):
		serializer = BookingRequestSerializer(data=request.data)
		if not serializer.is_valid():
			fields = {
				field: [str(error) for error in errors]
				for field, errors in serializer.errors.items()
			}
			message = next(iter(fields.values()))[0]
			return _error_response('VALIDATION_ERROR', message, fields)

		result = BookingService().create(serializer.validated_data)
		return Response(BookingResponseSerializer(result.booking).data, status=status.HTTP_201_CREATED)

	def get(self, request, booking_id):
		try:
			result = BookingService().get(booking_id)
		except Booking.DoesNotExist:
			return _error_response('BOOKING_NOT_FOUND', 'Booking not found.', http_status=status.HTTP_404_NOT_FOUND)
		return Response(BookingResponseSerializer(result.booking).data)


class UploadAPIView(APIView):
	def post(self, request):
		serializer = UploadRequestSerializer(data=request.data)
		try:
			serializer.is_valid(raise_exception=True)
		except NotFound as exc:
			return _error_response(
				'CONVERSATION_NOT_FOUND',
				str(exc.detail),
				http_status=status.HTTP_404_NOT_FOUND,
			)
		except Exception:
			if serializer.errors:
				fields = {
					field: [str(error) for error in errors]
					for field, errors in serializer.errors.items()
				}
				message = next(iter(fields.values()))[0]
				return _error_response('VALIDATION_ERROR', message, fields)
			raise

		try:
			result = MediaUploadService().upload(
				conversation_id=serializer.validated_data['conversation_id'],
				uploaded_file=serializer.validated_data['file'],
			)
		except MediaUploadError as exc:
			return _error_response(exc.code, exc.message, http_status=exc.http_status)
		except Exception:
			return _error_response(
				'INTERNAL_ERROR',
				'An unexpected error occurred while uploading the file.',
				http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)

		return Response(UploadResponseSerializer(result.data).data, status=status.HTTP_201_CREATED)
