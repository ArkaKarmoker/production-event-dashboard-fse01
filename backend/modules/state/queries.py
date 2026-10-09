"""Queries and calculations for state summary, pending review, and exceptions."""

from typing import Dict, Any, List, Optional
from django.db.models import Sum
from modules.events.models import ProductionEvent, SubmissionAttempt


class StateQueries:
    @staticmethod
    def get_summary(source_id: Optional[str] = None) -> Dict[str, int]:
        """
        Calculates the 6 required state indicators from durable PostgreSQL storage.
        """
        events_qs = ProductionEvent.objects.all()
        attempts_qs = SubmissionAttempt.objects.all()

        if source_id:
            events_qs = events_qs.filter(source_id=source_id)
            attempts_qs = attempts_qs.filter(source_id=source_id)

        # 1. net_total: Sum of accepted COUNT quantities minus successfully applied VOID quantities
        # In our model, active non-voided accepted counts represent the net valid count.
        active_counts_total = events_qs.filter(
            type="COUNT",
            status="ACCEPTED",
            is_voided=False
        ).aggregate(total=Sum("quantity"))["total"] or 0

        # 2. processed_events: Distinct completed COUNT and VOID events (unresolved joins after resolution)
        processed_events_count = events_qs.filter(
            status="ACCEPTED"
        ).count()

        # 3. pending_ack: Successfully processed events not yet acknowledged
        # Per specification note, completed VOIDs are auto-acknowledged, so this counts unreviewed COUNTs
        pending_ack_count = events_qs.filter(
            type="COUNT",
            status="ACCEPTED",
            acknowledged_at__isnull=True
        ).count()

        # 4. unresolved: Valid VOID events still waiting for target COUNT
        unresolved_count = events_qs.filter(
            type="VOID",
            status="PENDING_REFERENCE"
        ).count()

        # 5. duplicates: Number of stored identical duplicate submission attempts
        duplicates_count = attempts_qs.filter(
            classification="DUPLICATE"
        ).count()

        # 6. conflicts: Number of stored conflicting submission attempts
        conflicts_count = attempts_qs.filter(
            classification="CONFLICT"
        ).count()

        return {
            "net_total": active_counts_total,
            "processed_events": processed_events_count,
            "pending_ack": pending_ack_count,
            "unresolved": unresolved_count,
            "duplicates": duplicates_count,
            "conflicts": conflicts_count,
        }

    @staticmethod
    def get_pending(source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Successfully processed events ready for acknowledgement and not yet acknowledged.
        """
        qs = ProductionEvent.objects.filter(
            type="COUNT",
            status="ACCEPTED",
            acknowledged_at__isnull=True
        ).order_by("-received_at")

        if source_id:
            qs = qs.filter(source_id=source_id)

        results = []
        for e in qs:
            results.append({
                "event_id": e.event_id,
                "source_id": e.source_id,
                "type": e.type,
                "quantity": e.quantity,
                "target_event_id": e.target_event_id,
                "event_time": e.event_time.isoformat() if e.event_time else None,
                "received_at": e.received_at.isoformat() if e.received_at else None,
                "status": e.status,
                "is_voided": e.is_voided,
                "acknowledged_at": e.acknowledged_at.isoformat() if e.acknowledged_at else None,
            })
        return results

    @staticmethod
    def get_exceptions(source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Unresolved references, rejected submissions, and conflict attempts with reasons.
        """
        exceptions_list = []

        # 1. Unresolved pending references
        unresolved_qs = ProductionEvent.objects.filter(
            type="VOID",
            status="PENDING_REFERENCE"
        ).order_by("-received_at")

        if source_id:
            unresolved_qs = unresolved_qs.filter(source_id=source_id)

        for u in unresolved_qs:
            exceptions_list.append({
                "category": "UNRESOLVED_REFERENCE",
                "event_id": u.event_id,
                "source_id": u.source_id,
                "target_event_id": u.target_event_id,
                "reason": f"Waiting for target COUNT event {u.target_event_id}",
                "timestamp": u.received_at.isoformat() if u.received_at else None,
                "raw_payload": u.raw_payload,
            })

        # 2. Rejected submissions and Conflicts from attempts
        attempts_qs = SubmissionAttempt.objects.filter(
            classification__in=["REJECTED", "CONFLICT"]
        ).order_by("-received_at")

        if source_id:
            # Note: Invalid submissions without a useful source_id appear only in unfiltered exceptions
            attempts_qs = attempts_qs.filter(source_id=source_id)

        for a in attempts_qs:
            exceptions_list.append({
                "category": a.classification,
                "event_id": a.event_id or "UNKNOWN",
                "source_id": a.source_id or "UNKNOWN",
                "target_event_id": (a.raw_payload or {}).get("target_event_id"),
                "reason": a.error_message or "Validation or conflict error",
                "timestamp": a.received_at.isoformat() if a.received_at else None,
                "raw_payload": a.raw_payload,
            })

        # Sort all exceptions by timestamp descending
        exceptions_list.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        return exceptions_list
