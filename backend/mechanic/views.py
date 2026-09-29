from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ChatRequestSerializer, ChatResponseSerializer
from .services.chat_service import ChatService


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
