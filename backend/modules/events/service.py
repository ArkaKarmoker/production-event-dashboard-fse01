"""Core event processing engine for production events (COUNT & VOID)."""

from typing import Dict, Any, List, Union
from django.db import transaction
from django.utils import timezone
from .validation import validate_event
from .repository import EventRepository
from .models import compute_payload_hash
from modules.shared import domain_events


class EventService:
    @staticmethod
    def process_single_event(raw_data: Any) -> Dict[str, Any]:
        """
        Process a single event object with transactional safety.
        Returns: { "event_id": str, "status": str, "message": str }
        """
        raw_event_id = raw_data.get("event_id") if isinstance(raw_data, dict) else "UNKNOWN"
        raw_source_id = raw_data.get("source_id") if isinstance(raw_data, dict) else None

        # 1. Structural Validation
        is_valid, validated_data, error_msg = validate_event(raw_data)
        if not is_valid:
            EventRepository.record_attempt(
                source_id=raw_source_id,
                event_id=raw_event_id,
                raw_payload=raw_data if isinstance(raw_data, dict) else {"raw": str(raw_data)},
                classification="REJECTED",
                error_message=error_msg or "Invalid event structure"
            )
            return {
                "event_id": raw_event_id,
                "status": "REJECTED",
                "message": error_msg or "Validation failed"
            }

        source_id = validated_data["source_id"]
        event_id = validated_data["event_id"]
        event_type = validated_data["type"]
        quantity = validated_data.get("quantity")
        target_event_id = validated_data.get("target_event_id")
        event_time = validated_data["event_time"]

        # Ensure source exists
        EventRepository.get_or_create_source(source_id)

        # 2. Check for Duplicate or Conflict
        # Using atomic block with row locking to prevent race conditions
        with transaction.atomic():
            existing = EventRepository.get_event_for_update(source_id, event_id)
            if existing:
                new_hash = compute_payload_hash(raw_data)
                if existing.normalized_payload_hash == new_hash:
                    # Identical duplicate
                    EventRepository.record_attempt(
                        source_id=source_id,
                        event_id=event_id,
                        raw_payload=raw_data,
                        classification="DUPLICATE",
                        error_message="Identical duplicate event payload received"
                    )
                    return {
                        "event_id": event_id,
                        "status": "DUPLICATE",
                        "message": "Duplicate event received; already processed"
                    }
                else:
                    # Conflicting payload with same ID
                    EventRepository.record_attempt(
                        source_id=source_id,
                        event_id=event_id,
                        raw_payload=raw_data,
                        classification="CONFLICT",
                        error_message="Conflicting data received for existing event ID"
                    )
                    return {
                        "event_id": event_id,
                        "status": "CONFLICT",
                        "message": "Conflicting event data for existing event ID"
                    }

            # 3. Process COUNT Event
            if event_type == "COUNT":
                # Create the COUNT event
                count_event = EventRepository.create_event(
                    source_id=source_id,
                    event_id=event_id,
                    event_type="COUNT",
                    quantity=quantity,
                    target_event_id=None,
                    event_time=event_time,
                    status="ACCEPTED",
                    raw_payload=raw_data,
                    acknowledged_at=None  # Pending supervisor review
                )

                EventRepository.record_attempt(
                    source_id=source_id,
                    event_id=event_id,
                    raw_payload=raw_data,
                    classification="ACCEPTED"
                )

                # Check if any VOID arrived beforehand targeting this COUNT
                pending_voids = EventRepository.get_pending_voids_for_target(source_id, event_id)
                if pending_voids:
                    # First stored valid VOID wins
                    winning_void = pending_voids[0]
                    winning_void.status = "ACCEPTED"
                    winning_void.acknowledged_at = timezone.now()  # VOID is auto-acknowledged
                    winning_void.save()

                    count_event.is_voided = True
                    count_event.voided_by_event_id = winning_void.event_id
                    count_event.save()

                    domain_events.emit(domain_events.VOID_RESOLVED, {
                        "source_id": source_id,
                        "count_event_id": event_id,
                        "void_event_id": winning_void.event_id
                    })

                    # Reject any subsequent pending voids targeting the same COUNT
                    for surplus_void in pending_voids[1:]:
                        surplus_void.status = "REJECTED"
                        surplus_void.save()
                        EventRepository.record_attempt(
                            source_id=source_id,
                            event_id=surplus_void.event_id,
                            raw_payload=surplus_void.raw_payload,
                            classification="REJECTED",
                            error_message=f"Target COUNT already voided by winning VOID {winning_void.event_id}"
                        )

                domain_events.emit(domain_events.EVENT_ACCEPTED, {
                    "source_id": source_id,
                    "event_id": event_id,
                    "type": "COUNT",
                    "quantity": quantity
                })

                return {
                    "event_id": event_id,
                    "status": "ACCEPTED",
                    "message": "Event processed"
                }

            # 4. Process VOID Event
            elif event_type == "VOID":
                # Look for target COUNT event
                target_count = EventRepository.get_event_for_update(source_id, target_event_id)

                if target_count is None:
                    # Target COUNT has not arrived yet: store as PENDING_REFERENCE
                    EventRepository.create_event(
                        source_id=source_id,
                        event_id=event_id,
                        event_type="VOID",
                        quantity=None,
                        target_event_id=target_event_id,
                        event_time=event_time,
                        status="PENDING_REFERENCE",
                        raw_payload=raw_data,
                        acknowledged_at=None
                    )
                    EventRepository.record_attempt(
                        source_id=source_id,
                        event_id=event_id,
                        raw_payload=raw_data,
                        classification="PENDING_REFERENCE",
                        error_message=f"Target COUNT {target_event_id} not yet received"
                    )
                    return {
                        "event_id": event_id,
                        "status": "PENDING_REFERENCE",
                        "message": "Target event not found; stored as pending reference"
                    }

                # Target COUNT exists: verify rules
                if target_count.type != "COUNT":
                    EventRepository.record_attempt(
                        source_id=source_id,
                        event_id=event_id,
                        raw_payload=raw_data,
                        classification="REJECTED",
                        error_message="Target event is not a COUNT event"
                    )
                    return {
                        "event_id": event_id,
                        "status": "REJECTED",
                        "message": "Target event is not a COUNT event"
                    }

                if target_count.is_voided:
                    # Already voided
                    EventRepository.record_attempt(
                        source_id=source_id,
                        event_id=event_id,
                        raw_payload=raw_data,
                        classification="REJECTED",
                        error_message=f"Target event already voided by {target_count.voided_by_event_id}"
                    )
                    return {
                        "event_id": event_id,
                        "status": "REJECTED",
                        "message": f"Target event already voided by {target_count.voided_by_event_id}"
                    }

                # Apply VOID to target COUNT
                target_count.is_voided = True
                target_count.voided_by_event_id = event_id
                target_count.save()

                # VOID record created as ACCEPTED and auto-acknowledged
                EventRepository.create_event(
                    source_id=source_id,
                    event_id=event_id,
                    event_type="VOID",
                    quantity=None,
                    target_event_id=target_event_id,
                    event_time=event_time,
                    status="ACCEPTED",
                    raw_payload=raw_data,
                    acknowledged_at=timezone.now()
                )

                EventRepository.record_attempt(
                    source_id=source_id,
                    event_id=event_id,
                    raw_payload=raw_data,
                    classification="ACCEPTED"
                )

                domain_events.emit(domain_events.VOID_RESOLVED, {
                    "source_id": source_id,
                    "count_event_id": target_event_id,
                    "void_event_id": event_id
                })

                return {
                    "event_id": event_id,
                    "status": "ACCEPTED",
                    "message": "Event processed"
                }

        # Fallback (should not be reached)
        return {
            "event_id": raw_event_id,
            "status": "REJECTED",
            "message": "Unhandled event condition"
        }

    @classmethod
    def process_batch(cls, items: Union[List[Any], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a batch or single event item preserving submitted order.
        Each item is processed atomically; an invalid item is REJECTED without rolling back valid items.
        """
        if isinstance(items, dict):
            items_list = [items]
        elif isinstance(items, list):
            items_list = items
        else:
            return {"results": []}

        results = []
        for item in items_list:
            res = cls.process_single_event(item)
            results.append(res)

        return {"results": results}
