from dataclasses import dataclass
from typing import Any

from django.db import transaction

from ..models import Booking


@dataclass(frozen=True)
class BookingServiceResult:
	booking: Booking


class BookingService:
	"""Create and retrieve bookings associated with finalized diagnoses."""

	@transaction.atomic
	def create(self, validated_data: dict[str, Any]) -> BookingServiceResult:
		diagnosis = validated_data.pop('_diagnosis')
		booking = Booking.objects.create(
			diagnosis=diagnosis,
			conversation_id=validated_data.pop('conversation_id'),
			**validated_data,
		)
		return BookingServiceResult(booking)

	def get(self, booking_id: int) -> BookingServiceResult:
		return BookingServiceResult(
			Booking.objects.select_related('diagnosis', 'conversation').get(pk=booking_id)
		)