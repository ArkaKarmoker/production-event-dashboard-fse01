"""MQTT challenge validation and protocol response formatting."""

import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from django.utils import timezone
from modules.shared.contracts import (
    MQTT_COMMAND_PROCESS_EVENTS,
    MQTT_STATUS_COMPLETED,
    MQTT_STATUS_FAILED,
    ERROR_VALIDATION_ERROR,
    ERROR_CANDIDATE_MISMATCH,
    ERROR_UNSUPPORTED_PROTOCOL,
    ERROR_CHALLENGE_EXPIRED,
    ERROR_CHALLENGE_CONFLICT,
)


def compute_request_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


class ChallengeValidator:
    @staticmethod
    def validate_envelope(
        payload: Any,
        expected_candidate_id: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validates challenge envelope.
        Returns: (is_valid, error_code, error_message)
        """
        if not isinstance(payload, dict):
            return False, ERROR_VALIDATION_ERROR, "Payload must be a JSON object"

        # 1. Protocol Version
        protocol_version = payload.get("protocol_version")
        if protocol_version != "1.0":
            return False, ERROR_UNSUPPORTED_PROTOCOL, f"Unsupported protocol version: {protocol_version}"

        # 2. Candidate ID
        candidate_id = str(payload.get("candidate_id") or "")
        clean_expected = str(expected_candidate_id).strip()
        # Accept "12" or "CAND-012" or matching substring
        if candidate_id != clean_expected and not candidate_id.endswith(clean_expected):
            return False, ERROR_CANDIDATE_MISMATCH, f"Candidate mismatch. Expected {clean_expected}, got {candidate_id}"

        # 3. Challenge ID
        challenge_id = payload.get("challenge_id")
        if not challenge_id or not isinstance(challenge_id, str):
            return False, ERROR_VALIDATION_ERROR, "Missing or invalid challenge_id"

        # 4. Command
        command = payload.get("command")
        if command != MQTT_COMMAND_PROCESS_EVENTS:
            return False, ERROR_VALIDATION_ERROR, f"Unknown command: {command}"

        # 5. Expiry Check
        expires_at_str = payload.get("expires_at")
        if expires_at_str:
            try:
                # Handle ISO timestamps with Z or offset
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                if timezone.now() > expires_at:
                    return False, ERROR_CHALLENGE_EXPIRED, f"Challenge expired at {expires_at_str}"
            except Exception:
                pass  # If unparseable timestamp, proceed or reject gracefully

        # 6. Events collection
        events = payload.get("events")
        if not isinstance(events, list):
            return False, ERROR_VALIDATION_ERROR, "'events' field must be a list"

        return True, None, None


class ResponseFormatter:
    @staticmethod
    def build_completed_response(
        candidate_id: str,
        challenge_id: str,
        results: list,
        current_state: dict
    ) -> dict:
        return {
            "protocol_version": "1.0",
            "candidate_id": candidate_id,
            "challenge_id": challenge_id,
            "status": MQTT_STATUS_COMPLETED,
            "processed_at": timezone.now().isoformat(),
            "results": results,
            "state": current_state
        }

    @staticmethod
    def build_failed_response(
        candidate_id: str,
        challenge_id: str,
        error_code: str,
        message: str
    ) -> dict:
        return {
            "protocol_version": "1.0",
            "candidate_id": candidate_id,
            "challenge_id": challenge_id,
            "status": MQTT_STATUS_FAILED,
            "error_code": error_code,
            "message": message,
            "processed_at": timezone.now().isoformat(),
        }
