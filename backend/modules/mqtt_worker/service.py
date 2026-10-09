"""MQTT Challenge execution service reusing EventService and StateService."""

import logging
from typing import Dict, Any, Tuple
from django.db import transaction
from django.utils import timezone
from modules.events.models import MqttChallenge
from modules.events.service import EventService
from modules.state.service import StateService
from modules.shared.contracts import ERROR_CHALLENGE_CONFLICT
from .protocol import ChallengeValidator, ResponseFormatter, compute_request_hash

logger = logging.getLogger(__name__)


class MqttChallengeService:
    @staticmethod
    def handle_challenge(payload: dict, expected_candidate_id: str) -> Tuple[dict, str]:
        """
        Processes an incoming challenge payload.
        Returns: (response_dict, status_string)
        """
        challenge_id = payload.get("challenge_id") or "UNKNOWN_CHALLENGE"
        candidate_id = payload.get("candidate_id") or expected_candidate_id

        # 1. Envelope validation
        is_valid, err_code, err_msg = ChallengeValidator.validate_envelope(payload, expected_candidate_id)
        if not is_valid:
            resp = ResponseFormatter.build_failed_response(
                candidate_id=candidate_id,
                challenge_id=challenge_id,
                error_code=err_code or "VALIDATION_ERROR",
                message=err_msg or "Invalid challenge envelope"
            )
            return resp, "FAILED"

        # 2. Replay & Idempotency check with DB locking
        request_hash = compute_request_hash(payload)

        with transaction.atomic():
            existing_challenge = MqttChallenge.objects.filter(challenge_id=challenge_id).first()

            if existing_challenge:
                if existing_challenge.request_hash == request_hash:
                    # Same challenge_id + same payload: return original response without reprocessing
                    logger.info(f"Replay detected for challenge {challenge_id}. Returning saved response.")
                    return existing_challenge.response_payload, existing_challenge.status
                else:
                    # Same challenge_id + different payload: FAILED / CHALLENGE_CONFLICT
                    logger.warning(f"Conflict detected for challenge {challenge_id}.")
                    resp = ResponseFormatter.build_failed_response(
                        candidate_id=candidate_id,
                        challenge_id=challenge_id,
                        error_code=ERROR_CHALLENGE_CONFLICT,
                        message="Challenge ID already processed with different payload"
                    )
                    return resp, "FAILED"

            # 3. Process events through shared EventService
            events_list = payload.get("events", [])
            batch_result = EventService.process_batch(events_list)

            # 4. Read state through shared StateService
            current_state = StateService.get_summary()

            # 5. Build response
            response_payload = ResponseFormatter.build_completed_response(
                candidate_id=candidate_id,
                challenge_id=challenge_id,
                results=batch_result.get("results", []),
                current_state=current_state
            )

            # 6. Persist challenge record in PostgreSQL
            MqttChallenge.objects.create(
                challenge_id=challenge_id,
                protocol_version=payload.get("protocol_version", "1.0"),
                candidate_id=candidate_id,
                command=payload.get("command", "PROCESS_EVENTS"),
                request_body=payload,
                request_hash=request_hash,
                response_payload=response_payload,
                status="COMPLETED",
                processed_at=timezone.now(),
            )

            return response_payload, "COMPLETED"
