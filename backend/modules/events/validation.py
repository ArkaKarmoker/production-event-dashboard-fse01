"""Validation module for production events."""

from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from rest_framework import serializers


class EventSerializer(serializers.Serializer):
    source_id = serializers.CharField(max_length=64, required=True, allow_blank=False)
    event_id = serializers.CharField(max_length=128, required=True, allow_blank=False)
    type = serializers.ChoiceField(choices=["COUNT", "VOID"], required=True)
    quantity = serializers.IntegerField(required=False, allow_null=True)
    target_event_id = serializers.CharField(max_length=128, required=False, allow_null=True, allow_blank=False)
    event_time = serializers.DateTimeField(required=True)

    def validate(self, attrs):
        event_type = attrs.get("type")
        quantity = attrs.get("quantity")
        target_event_id = attrs.get("target_event_id")

        if event_type == "COUNT":
            if quantity is None:
                raise serializers.ValidationError({"quantity": "Quantity is required for COUNT event."})
            if quantity <= 0:
                raise serializers.ValidationError({"quantity": "Quantity must be a positive integer."})
            if target_event_id:
                raise serializers.ValidationError({"target_event_id": "target_event_id must be null or omitted for COUNT event."})

        elif event_type == "VOID":
            if quantity is not None:
                raise serializers.ValidationError({"quantity": "Quantity must be null or omitted for VOID event."})
            if not target_event_id:
                raise serializers.ValidationError({"target_event_id": "target_event_id is required for VOID event."})

        return attrs


def validate_event(raw_data: Any) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate a single event object.
    Returns: (is_valid, validated_data, error_message)
    """
    if not isinstance(raw_data, dict):
        return False, None, "Item must be a JSON object"

    serializer = EventSerializer(data=raw_data)
    if serializer.is_valid():
        return True, serializer.validated_data, None
    else:
        # Format serializer errors into a readable string
        errors = serializer.errors
        error_parts = []
        for field, err_list in errors.items():
            if isinstance(err_list, list):
                error_parts.append(f"{field}: {err_list[0]}")
            else:
                error_parts.append(f"{field}: {err_list}")
        return False, None, "; ".join(error_parts)
