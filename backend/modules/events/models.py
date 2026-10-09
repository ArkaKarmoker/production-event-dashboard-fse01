import hashlib
import json
from django.db import models
from django.utils import timezone


def compute_payload_hash(payload: dict) -> str:
    """Compute deterministic SHA-256 hash of normalized payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


class ProductionSource(models.Model):
    """Represents a production source or machine (e.g. LINE-01)."""
    source_id = models.CharField(max_length=64, primary_key=True)
    display_name = models.CharField(max_length=128, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "production_sources"
        verbose_name = "Production Source"
        verbose_name_plural = "Production Sources"

    def __str__(self):
        return self.source_id


class ProductionEvent(models.Model):
    """Core production event record (COUNT or VOID)."""
    STATUS_CHOICES = [
        ("ACCEPTED", "Accepted"),
        ("PENDING_REFERENCE", "Pending Reference"),
        ("RESOLVED", "Resolved"),
        ("REJECTED", "Rejected"),
    ]

    TYPE_CHOICES = [
        ("COUNT", "Count"),
        ("VOID", "Void"),
    ]

    event_id = models.CharField(max_length=128, db_index=True)
    source_id = models.CharField(max_length=64, db_index=True)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES, db_index=True)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    target_event_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    event_time = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="ACCEPTED", db_index=True)
    is_voided = models.BooleanField(default=False)
    voided_by_event_id = models.CharField(max_length=128, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True, db_index=True)
    acknowledged_by = models.CharField(max_length=64, default="", blank=True)
    raw_payload = models.JSONField(default=dict)
    normalized_payload_hash = models.CharField(max_length=64, db_index=True)

    class Meta:
        db_table = "production_events"
        constraints = [
            models.UniqueConstraint(
                fields=["source_id", "event_id"],
                name="unique_source_event"
            )
        ]
        indexes = [
            models.Index(fields=["source_id", "status"]),
            models.Index(fields=["type", "status"]),
        ]

    def __str__(self):
        return f"{self.source_id}:{self.event_id} ({self.type}) - {self.status}"


class SubmissionAttempt(models.Model):
    """Audit log of every submission attempt (valid, duplicate, conflict, rejected)."""
    CLASSIFICATION_CHOICES = [
        ("ACCEPTED", "Accepted"),
        ("DUPLICATE", "Duplicate"),
        ("CONFLICT", "Conflict"),
        ("PENDING_REFERENCE", "Pending Reference"),
        ("REJECTED", "Rejected"),
    ]

    source_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    event_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    raw_payload = models.JSONField(default=dict)
    classification = models.CharField(max_length=32, choices=CLASSIFICATION_CHOICES, db_index=True)
    error_message = models.TextField(blank=True, default="")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "submission_attempts"
        indexes = [
            models.Index(fields=["source_id", "classification"]),
            models.Index(fields=["received_at"]),
        ]

    def __str__(self):
        return f"{self.event_id or 'UNKNOWN'} - {self.classification} at {self.received_at}"


class MqttChallenge(models.Model):
    """Store MQTT challenge requests and responses for deduplication & audit."""
    challenge_id = models.CharField(max_length=128, primary_key=True)
    protocol_version = models.CharField(max_length=32, default="1.0")
    candidate_id = models.CharField(max_length=64)
    command = models.CharField(max_length=64, default="PROCESS_EVENTS")
    request_body = models.JSONField(default=dict)
    request_hash = models.CharField(max_length=64, db_index=True)
    response_payload = models.JSONField(default=dict)
    status = models.CharField(max_length=32, default="COMPLETED")
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mqtt_challenges"

    def __str__(self):
        return f"{self.challenge_id} ({self.status})"
