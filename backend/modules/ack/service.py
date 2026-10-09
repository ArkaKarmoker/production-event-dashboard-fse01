"""Service layer for event acknowledgement workflow."""

from typing import List, Dict, Any
from django.db import transaction
from django.utils import timezone
from modules.events.models import ProductionEvent
from modules.shared.contracts import (
    ACK_STATUS_ACKED,
    ACK_STATUS_ALREADY_ACKED,
    ACK_STATUS_NOT_READY,
    ACK_STATUS_NOT_FOUND
)
from modules.shared import domain_events


class AckService:
    @staticmethod
    def acknowledge_events(event_ids: List[str]) -> List[Dict[str, str]]:
        """
        Process a list of event_ids in submitted order with transactional safety.
        Returns: [ { "event_id": str, "status": str } ]
        """
        results = []
        # Keep track of IDs processed in this batch to handle duplicates within the same request
        acked_in_this_batch = set()

        with transaction.atomic():
            for eid in event_ids:
                if not isinstance(eid, str) or not eid.strip():
                    results.append({"event_id": str(eid), "status": ACK_STATUS_NOT_FOUND})
                    continue

                event_id = eid.strip()

                # If this ID was already ACKED earlier in this batch
                if event_id in acked_in_this_batch:
                    results.append({"event_id": event_id, "status": ACK_STATUS_ALREADY_ACKED})
                    continue

                # Query the logical event with row locking
                event = ProductionEvent.objects.select_for_update().filter(event_id=event_id).first()

                if not event:
                    results.append({"event_id": event_id, "status": ACK_STATUS_NOT_FOUND})
                    continue

                if event.status == "PENDING_REFERENCE":
                    results.append({"event_id": event_id, "status": ACK_STATUS_NOT_READY})
                    continue

                if event.status == "REJECTED":
                    results.append({"event_id": event_id, "status": ACK_STATUS_NOT_READY})
                    continue

                if event.status in ["ACCEPTED", "RESOLVED"]:
                    if event.acknowledged_at is not None:
                        results.append({"event_id": event_id, "status": ACK_STATUS_ALREADY_ACKED})
                    else:
                        event.acknowledged_at = timezone.now()
                        event.acknowledged_by = "SUPERVISOR"
                        event.save()
                        acked_in_this_batch.add(event_id)

                        domain_events.emit(domain_events.EVENT_ACKNOWLEDGED, {
                            "event_id": event_id,
                            "source_id": event.source_id,
                            "acknowledged_at": event.acknowledged_at.isoformat()
                        })

                        results.append({"event_id": event_id, "status": ACK_STATUS_ACKED})
                else:
                    results.append({"event_id": event_id, "status": ACK_STATUS_NOT_READY})

        return results
