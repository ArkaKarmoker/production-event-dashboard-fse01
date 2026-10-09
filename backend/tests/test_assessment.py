"""Automated tests for CSI Smart Tech FSE 01 Candidate Assessment."""

import json
from datetime import datetime, timezone
from django.test import TestCase, Client
from django.urls import reverse
from modules.events.models import ProductionEvent, SubmissionAttempt, MqttChallenge
from modules.mqtt_worker.service import MqttChallengeService


class CandidateAssessmentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.candidate_id = "12"

    def test_1_count_and_total(self):
        """Test 1: COUNT adds its quantity to total upon successful processing."""
        payload = {
            "source_id": "LINE-01",
            "event_id": "EV-101",
            "type": "COUNT",
            "quantity": 5,
            "target_event_id": None,
            "event_time": "2026-10-09T10:30:00Z"
        }
        resp = self.client.post(
            "/api/events",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["event_id"], "EV-101")
        self.assertEqual(data["results"][0]["status"], "ACCEPTED")

        # Verify state summary
        state_resp = self.client.get("/api/state?view=summary")
        self.assertEqual(state_resp.status_code, 200)
        state_data = state_resp.json()
        self.assertEqual(state_data["net_total"], 5)
        self.assertEqual(state_data["processed_events"], 1)
        self.assertEqual(state_data["pending_ack"], 1)
        self.assertEqual(state_data["unresolved"], 0)

    def test_2_identical_duplicate_without_double_counting(self):
        """Test 2: Sending identical duplicate returns DUPLICATE and never double counts."""
        payload = {
            "source_id": "LINE-01",
            "event_id": "EV-102",
            "type": "COUNT",
            "quantity": 10,
            "target_event_id": None,
            "event_time": "2026-10-09T10:30:00Z"
        }
        # First submission
        resp1 = self.client.post("/api/events", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp1.json()["results"][0]["status"], "ACCEPTED")

        # Second submission (identical)
        resp2 = self.client.post("/api/events", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["results"][0]["status"], "DUPLICATE")

        # Verify state summary: net_total should remain 10, duplicates count is 1
        state_resp = self.client.get("/api/state?view=summary")
        state_data = state_resp.json()
        self.assertEqual(state_data["net_total"], 10)
        self.assertEqual(state_data["duplicates"], 1)

    def test_3_void_before_count_resolution(self):
        """Test 3: VOID-before-COUNT stored as PENDING_REFERENCE and auto-resolves when target arrives."""
        # 1. Send VOID before COUNT arrives
        void_payload = {
            "source_id": "LINE-01",
            "event_id": "VOID-201",
            "type": "VOID",
            "quantity": None,
            "target_event_id": "EV-201",
            "event_time": "2026-10-09T10:35:00Z"
        }
        void_resp = self.client.post("/api/events", data=json.dumps(void_payload), content_type="application/json")
        self.assertEqual(void_resp.status_code, 200)
        self.assertEqual(void_resp.json()["results"][0]["status"], "PENDING_REFERENCE")

        # Check state: unresolved is 1, net_total is 0
        state1 = self.client.get("/api/state?view=summary").json()
        self.assertEqual(state1["unresolved"], 1)
        self.assertEqual(state1["net_total"], 0)

        # 2. Matching target COUNT arrives later
        count_payload = {
            "source_id": "LINE-01",
            "event_id": "EV-201",
            "type": "COUNT",
            "quantity": 8,
            "target_event_id": None,
            "event_time": "2026-10-09T10:30:00Z"
        }
        count_resp = self.client.post("/api/events", data=json.dumps(count_payload), content_type="application/json")
        self.assertEqual(count_resp.status_code, 200)
        self.assertEqual(count_resp.json()["results"][0]["status"], "ACCEPTED")

        # 3. Check state after resolution: unresolved becomes 0, net_total is 0 because VOID reversed it!
        state2 = self.client.get("/api/state?view=summary").json()
        self.assertEqual(state2["unresolved"], 0)
        self.assertEqual(state2["net_total"], 0)  # Reversal was applied automatically!

    def test_4_repeated_acknowledgement(self):
        """Test 4: Repeated acknowledgement is safe, idempotent, and returns ALREADY_ACKED."""
        # Setup an accepted event
        self.client.post("/api/events", data=json.dumps({
            "source_id": "LINE-01",
            "event_id": "EV-301",
            "type": "COUNT",
            "quantity": 15,
            "event_time": "2026-10-09T10:30:00Z"
        }), content_type="application/json")

        # First ACK
        ack_resp1 = self.client.post("/api/ack", data=json.dumps({
            "event_ids": ["EV-301", "NON-EXISTENT"]
        }), content_type="application/json")
        self.assertEqual(ack_resp1.status_code, 200)
        results1 = ack_resp1.json()
        self.assertEqual(results1[0]["event_id"], "EV-301")
        self.assertEqual(results1[0]["status"], "ACKED")
        self.assertEqual(results1[1]["event_id"], "NON-EXISTENT")
        self.assertEqual(results1[1]["status"], "NOT_FOUND")

        # Second ACK (repeat)
        ack_resp2 = self.client.post("/api/ack", data=json.dumps({
            "event_ids": ["EV-301"]
        }), content_type="application/json")
        self.assertEqual(ack_resp2.status_code, 200)
        results2 = ack_resp2.json()
        self.assertEqual(results2[0]["status"], "ALREADY_ACKED")

    def test_5_repeated_mqtt_challenge_idempotency(self):
        """Test 5: Repeated MQTT challenge returns cached response without reprocessing."""
        challenge_payload = {
            "protocol_version": "1.0",
            "candidate_id": "12",
            "challenge_id": "CH-TEST-501",
            "command": "PROCESS_EVENTS",
            "sent_at": "2026-10-09T10:45:00Z",
            "expires_at": "2026-10-09T11:45:00Z",
            "events": [
                {
                    "source_id": "LINE-02",
                    "event_id": "EV-501",
                    "type": "COUNT",
                    "quantity": 25,
                    "target_event_id": None,
                    "event_time": "2026-10-09T10:30:00Z"
                }
            ]
        }

        # First execution
        resp1, status1 = MqttChallengeService.handle_challenge(challenge_payload, "12")
        self.assertEqual(status1, "COMPLETED")
        self.assertEqual(resp1["status"], "COMPLETED")
        self.assertEqual(resp1["results"][0]["status"], "ACCEPTED")
        net_after_first = resp1["state"]["net_total"]

        # Second execution (identical replay)
        resp2, status2 = MqttChallengeService.handle_challenge(challenge_payload, "12")
        self.assertEqual(status2, "COMPLETED")
        self.assertEqual(resp2["challenge_id"], "CH-TEST-501")
        # Net total should not increase!
        self.assertEqual(resp2["state"]["net_total"], net_after_first)

        # Third execution with conflicting body
        conflicting_payload = dict(challenge_payload)
        conflicting_payload["events"] = [
            {
                "source_id": "LINE-02",
                "event_id": "EV-502",
                "type": "COUNT",
                "quantity": 999,
                "event_time": "2026-10-09T10:30:00Z"
            }
        ]
        resp3, status3 = MqttChallengeService.handle_challenge(conflicting_payload, "12")
        self.assertEqual(status3, "FAILED")
        self.assertEqual(resp3["error_code"], "CHALLENGE_CONFLICT")

    def test_6_batch_processing_and_isolation(self):
        """Test 6: Invalid item in a batch is REJECTED while valid items succeed."""
        batch_payload = [
            {
                "source_id": "LINE-01",
                "event_id": "EV-601",
                "type": "COUNT",
                "quantity": 10,
                "event_time": "2026-10-09T10:30:00Z"
            },
            {
                "source_id": "LINE-01",
                "event_id": "EV-INVALID",
                "type": "COUNT",
                "quantity": -5,  # Invalid negative quantity
                "event_time": "2026-10-09T10:30:00Z"
            },
            {
                "source_id": "LINE-01",
                "event_id": "EV-602",
                "type": "COUNT",
                "quantity": 20,
                "event_time": "2026-10-09T10:30:00Z"
            }
        ]
        resp = self.client.post("/api/events", data=json.dumps(batch_payload), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["status"], "ACCEPTED")
        self.assertEqual(results[1]["status"], "REJECTED")
        self.assertEqual(results[2]["status"], "ACCEPTED")

    def test_7_conflict_detection(self):
        """Test 7: Same event_id with different payload triggers CONFLICT status."""
        p1 = {
            "source_id": "LINE-01",
            "event_id": "EV-701",
            "type": "COUNT",
            "quantity": 5,
            "event_time": "2026-10-09T10:30:00Z"
        }
        self.client.post("/api/events", data=json.dumps(p1), content_type="application/json")

        # Different quantity with same event_id
        p2 = dict(p1)
        p2["quantity"] = 99
        resp = self.client.post("/api/events", data=json.dumps(p2), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["results"][0]["status"], "CONFLICT")

        # Verify exceptions view includes CONFLICT
        ex_resp = self.client.get("/api/state?view=exceptions")
        ex_data = ex_resp.json()
        has_conflict = any(item.get("category") == "CONFLICT" for item in ex_data)
        self.assertTrue(has_conflict)

    def test_8_count_quantity_max_500_validation(self):
        """Test 8 (Change Request 01): COUNT quantity must be between 1 and 500 inclusive."""
        # 1. COUNT 450 -> ACCEPTED
        p_valid = {
            "source_id": "LINE-01",
            "event_id": "EV-801",
            "type": "COUNT",
            "quantity": 450,
            "target_event_id": None,
            "event_time": "2026-10-09T10:30:00Z"
        }
        resp_valid = self.client.post("/api/events", data=json.dumps(p_valid), content_type="application/json")
        self.assertEqual(resp_valid.status_code, 200)
        self.assertEqual(resp_valid.json()["results"][0]["status"], "ACCEPTED")

        # 2. COUNT 501 -> REJECTED (exceeds 500 limit)
        p_invalid = {
            "source_id": "LINE-01",
            "event_id": "EV-802",
            "type": "COUNT",
            "quantity": 501,
            "target_event_id": None,
            "event_time": "2026-10-09T10:30:00Z"
        }
        resp_invalid = self.client.post("/api/events", data=json.dumps(p_invalid), content_type="application/json")
        self.assertEqual(resp_invalid.status_code, 200)
        res_item = resp_invalid.json()["results"][0]
        self.assertEqual(res_item["status"], "REJECTED")
        self.assertIn("between 1 and 500", res_item["message"])

        # 3. Verify net total: only 450 should be counted, not 450 + 501
        summary = self.client.get("/api/state?view=summary").json()
        self.assertEqual(summary["net_total"], 450)
        # 4. Verify rejected_submissions count is 1
        self.assertEqual(summary["rejected_submissions"], 1)

    def test_9_rejected_submissions_in_summary_and_source_filter(self):
        """Test 9 (Change Request 02): rejected_submissions in summary, source filter, and MQTT state."""
        # Submit a rejected item for LINE-01
        self.client.post("/api/events", data=json.dumps({
            "source_id": "LINE-01",
            "event_id": "EV-901-REJ",
            "type": "COUNT",
            "quantity": 600,
            "event_time": "2026-10-09T10:30:00Z"
        }), content_type="application/json")

        # Submit a rejected item for LINE-02
        self.client.post("/api/events", data=json.dumps({
            "source_id": "LINE-02",
            "event_id": "EV-902-REJ",
            "type": "COUNT",
            "quantity": 550,
            "event_time": "2026-10-09T10:30:00Z"
        }), content_type="application/json")

        # Unfiltered summary (or /api/stats alias)
        summary_all = self.client.get("/api/state?view=summary").json()
        self.assertEqual(summary_all["rejected_submissions"], 2)

        summary_alias = self.client.get("/api/stats?view=summary").json()
        self.assertEqual(summary_alias["rejected_submissions"], 2)

        # Filtered by source_id=LINE-01
        summary_line1 = self.client.get("/api/state?source_id=LINE-01&view=summary").json()
        self.assertEqual(summary_line1["rejected_submissions"], 1)

        # Filtered by source_id=LINE-02
        summary_line2 = self.client.get("/api/state?source_id=LINE-02&view=summary").json()
        self.assertEqual(summary_line2["rejected_submissions"], 1)

        # Check MQTT challenge response includes rejected_submissions in state
        challenge_payload = {
            "protocol_version": "1.0",
            "candidate_id": "12",
            "challenge_id": "CH-TEST-901",
            "command": "PROCESS_EVENTS",
            "sent_at": "2026-10-09T10:45:00Z",
            "expires_at": "2026-10-09T11:45:00Z",
            "events": [
                {
                    "source_id": "LINE-01",
                    "event_id": "EV-MQTT-901",
                    "type": "COUNT",
                    "quantity": 100,
                    "target_event_id": None,
                    "event_time": "2026-10-09T10:30:00Z"
                }
            ]
        }
        resp, status = MqttChallengeService.handle_challenge(challenge_payload, "12")
        self.assertEqual(status, "COMPLETED")
        self.assertIn("rejected_submissions", resp["state"])

