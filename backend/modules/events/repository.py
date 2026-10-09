"""Data access repository for production events, sources, and attempts."""

from typing import Optional, List
from django.db import transaction
from django.utils import timezone
from .models import ProductionSource, ProductionEvent, SubmissionAttempt, compute_payload_hash


class EventRepository:
    @staticmethod
    def get_or_create_source(source_id: str) -> ProductionSource:
        source, _ = ProductionSource.objects.get_or_create(
            source_id=source_id,
            defaults={"display_name": source_id}
        )
        return source

    @staticmethod
    def record_attempt(
        source_id: Optional[str],
        event_id: Optional[str],
        raw_payload: dict,
        classification: str,
        error_message: str = ""
    ) -> SubmissionAttempt:
        return SubmissionAttempt.objects.create(
            source_id=source_id,
            event_id=event_id,
            raw_payload=raw_payload,
            classification=classification,
            error_message=error_message
        )

    @staticmethod
    def find_existing_event(source_id: str, event_id: str) -> Optional[ProductionEvent]:
        return ProductionEvent.objects.filter(source_id=source_id, event_id=event_id).first()

    @staticmethod
    def find_existing_event_by_id(event_id: str) -> Optional[ProductionEvent]:
        return ProductionEvent.objects.filter(event_id=event_id).first()

    @staticmethod
    def get_event_for_update(source_id: str, event_id: str) -> Optional[ProductionEvent]:
        return ProductionEvent.objects.select_for_update().filter(
            source_id=source_id, event_id=event_id
        ).first()

    @staticmethod
    def create_event(
        source_id: str,
        event_id: str,
        event_type: str,
        quantity: Optional[int],
        target_event_id: Optional[str],
        event_time,
        status: str,
        raw_payload: dict,
        acknowledged_at=None
    ) -> ProductionEvent:
        payload_hash = compute_payload_hash(raw_payload)
        return ProductionEvent.objects.create(
            source_id=source_id,
            event_id=event_id,
            type=event_type,
            quantity=quantity,
            target_event_id=target_event_id,
            event_time=event_time,
            status=status,
            raw_payload=raw_payload,
            normalized_payload_hash=payload_hash,
            acknowledged_at=acknowledged_at
        )

    @staticmethod
    def get_pending_voids_for_target(source_id: str, target_event_id: str) -> List[ProductionEvent]:
        """Fetch pending voids ordered by arrival (first stored wins)."""
        return list(ProductionEvent.objects.select_for_update().filter(
            source_id=source_id,
            target_event_id=target_event_id,
            type="VOID",
            status="PENDING_REFERENCE"
        ).order_by("id"))
