import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction

from ..models import Conversation, MediaAttachment, Message


class MediaUploadError(Exception):
    def __init__(self, code: str, message: str, http_status: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


@dataclass(frozen=True)
class MediaUploadResult:
    data: dict[str, Any]


class MediaUploadService:
    """Validate and persist one conversation media attachment."""

    _IMAGE_TYPES = {
        '.jpg': ('image', {'image/jpeg'}),
        '.jpeg': ('image', {'image/jpeg'}),
        '.png': ('image', {'image/png'}),
        '.webp': ('image', {'image/webp'}),
    }
    _AUDIO_TYPES = {
        '.mp3': ('audio', {'audio/mpeg', 'audio/mp3'}),
        '.wav': ('audio', {'audio/wav', 'audio/x-wav', 'audio/wave'}),
        '.ogg': ('audio', {'audio/ogg'}),
    }
    _VIDEO_TYPES = {
        '.mp4': ('video', {'video/mp4'}),
        '.mov': ('video', {'video/quicktime', 'video/mp4'}),
    }

    def __init__(self, max_upload_size_bytes: int | None = None) -> None:
        self.max_upload_size_bytes = max_upload_size_bytes or settings.MAX_UPLOAD_SIZE_BYTES

    @transaction.atomic
    def upload(self, conversation_id, uploaded_file) -> MediaUploadResult:
        conversation = self._get_conversation(conversation_id)
        media_type = self._validate_file(uploaded_file)
        message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content=f'{media_type.title()} attachment',
            message_type=media_type,
        )
        stored_name = None
        try:
            attachment = MediaAttachment(
                conversation=conversation,
                message=message,
                file_type=media_type,
                file_size=uploaded_file.size,
            )
            requested_name = self._stored_name(uploaded_file.name)
            attachment.file.save(requested_name, uploaded_file, save=False)
            stored_name = attachment.file.name
            attachment.file_size = uploaded_file.size
            attachment.save()
        except Exception:
            if stored_name:
                default_storage.delete(stored_name)
            raise

        return MediaUploadResult({
            'conversation_id': str(conversation.id),
            'message_id': message.id,
            'attachment': {
                'id': attachment.id,
                'file_type': attachment.file_type,
                'file_size': attachment.file_size,
                'url': attachment.file.url,
                'filename': Path(attachment.file.name).name,
            },
        })

    def _get_conversation(self, conversation_id):
        try:
            return Conversation.objects.get(pk=conversation_id)
        except Conversation.DoesNotExist as exc:
            raise MediaUploadError(
                'CONVERSATION_NOT_FOUND',
                'Conversation not found.',
                404,
            ) from exc

    def _validate_file(self, uploaded_file) -> str:
        if uploaded_file is None:
            raise MediaUploadError('FILE_REQUIRED', 'A file is required.', 400)
        if uploaded_file.size > self.max_upload_size_bytes:
            raise MediaUploadError(
                'FILE_TOO_LARGE',
                f'File must be {self.max_upload_size_bytes // (1024 * 1024)} MB or smaller.',
                413,
            )

        filename = str(uploaded_file.name or '')
        if not self._is_safe_filename(filename):
            raise MediaUploadError('INVALID_FILENAME', 'The filename is invalid.', 400)

        suffix = Path(filename).suffix.lower()
        specifications = {**self._IMAGE_TYPES, **self._AUDIO_TYPES, **self._VIDEO_TYPES}
        if suffix not in specifications and suffix != '.webm':
            raise MediaUploadError('UNSUPPORTED_MEDIA_TYPE', 'This file type is not supported.', 415)

        header = uploaded_file.read(32)
        uploaded_file.seek(0)
        media_type, accepted_content_types = self._specification_for(suffix, uploaded_file.content_type)
        declared_type = (uploaded_file.content_type or '').lower()
        if declared_type and declared_type != 'application/octet-stream' and declared_type not in accepted_content_types:
            raise MediaUploadError('UNSUPPORTED_MEDIA_TYPE', 'The file type does not match its extension.', 415)
        if not self._has_expected_signature(suffix, header):
            raise MediaUploadError('UNSUPPORTED_MEDIA_TYPE', 'The file content is not valid for its extension.', 415)
        return media_type

    def _specification_for(self, suffix: str, content_type: str | None):
        if suffix in self._IMAGE_TYPES:
            return self._IMAGE_TYPES[suffix]
        if suffix in self._AUDIO_TYPES:
            return self._AUDIO_TYPES[suffix]
        if suffix in self._VIDEO_TYPES:
            return self._VIDEO_TYPES[suffix]
        if suffix == '.webm':
            declared_type = (content_type or '').lower()
            if declared_type == 'audio/webm':
                return 'audio', {'audio/webm'}
            if declared_type == 'video/webm':
                return 'video', {'video/webm'}
        raise MediaUploadError('UNSUPPORTED_MEDIA_TYPE', 'A WEBM file must declare audio or video.', 415)

    def _has_expected_signature(self, suffix: str, header: bytes) -> bool:
        if suffix in {'.jpg', '.jpeg'}:
            return header.startswith(b'\xff\xd8\xff')
        if suffix == '.png':
            return header.startswith(b'\x89PNG\r\n\x1a\n')
        if suffix == '.webp':
            return header.startswith(b'RIFF') and header[8:12] == b'WEBP'
        if suffix == '.mp3':
            return header.startswith(b'ID3') or (
                len(header) > 1 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
            )
        if suffix == '.wav':
            return header.startswith(b'RIFF') and header[8:12] == b'WAVE'
        if suffix == '.ogg':
            return header.startswith(b'OggS')
        if suffix in {'.mp4', '.mov'}:
            return len(header) >= 8 and header[4:8] == b'ftyp'
        if suffix == '.webm':
            return header.startswith(b'\x1a\x45\xdf\xa3')
        return False

    def _is_safe_filename(self, filename: str) -> bool:
        return bool(
            filename
            and '\x00' not in filename
            and '/' not in filename
            and '\\' not in filename
            and '..' not in filename
            and os.path.basename(filename) == filename
        )

    def _stored_name(self, original_name: str) -> str:
        suffix = Path(original_name).suffix.lower()
        return f'{uuid.uuid4().hex}{suffix}'