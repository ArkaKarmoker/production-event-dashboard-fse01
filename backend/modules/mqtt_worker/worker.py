"""MQTT Worker implementation with paho-mqtt, auto-reconnect, and heartbeat."""

import json
import random
import string
import time
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import paho.mqtt.client as mqtt
from django.conf import settings
from django.utils import timezone
from .service import MqttChallengeService

logger = logging.getLogger(__name__)

# Global status tracker for frontend monitoring
_worker_state = {
    "is_connected": False,
    "broker_host": "",
    "broker_port": 1883,
    "candidate_id": "12",
    "client_id": "",
    "connected_at": None,
    "last_heartbeat_at": None,
    "last_challenge_id": None,
    "last_challenge_time": None,
    "last_response_status": None,
    "total_challenges_received": 0,
    "last_error": None,
}

_worker_thread = None
_heartbeat_thread = None
_client_instance: Optional[mqtt.Client] = None
_stop_event = threading.Event()


def get_worker_status() -> Dict[str, Any]:
    return dict(_worker_state)


def generate_client_id(candidate_id: str) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"fse01-{candidate_id}-{suffix}"


def _heartbeat_loop(client: mqtt.Client, candidate_id: str):
    status_topic = f"fse-01/{candidate_id}/status"
    while not _stop_event.is_set():
        if _worker_state["is_connected"]:
            try:
                hb_payload = {
                    "status": "HEARTBEAT",
                    "candidate_id": candidate_id,
                    "timestamp": timezone.now().isoformat()
                }
                client.publish(status_topic, json.dumps(hb_payload), qos=1, retain=False)
                _worker_state["last_heartbeat_at"] = timezone.now().isoformat()
            except Exception as e:
                logger.error(f"Failed to publish heartbeat: {e}")
        # Sleep up to 30 seconds (checking stop event every second)
        for _ in range(30):
            if _stop_event.is_set():
                break
            time.sleep(1)


def _on_connect(client, userdata, flags, rc, properties=None):
    candidate_id = userdata.get("candidate_id", "12")
    if rc == 0:
        logger.info(f"MQTT Connected successfully as {client._client_id}")
        _worker_state["is_connected"] = True
        _worker_state["connected_at"] = timezone.now().isoformat()
        _worker_state["last_error"] = None

        # Publish ONLINE status
        status_topic = f"fse-01/{candidate_id}/status"
        online_payload = {
            "status": "ONLINE",
            "candidate_id": candidate_id,
            "timestamp": timezone.now().isoformat()
        }
        client.publish(status_topic, json.dumps(online_payload), qos=1, retain=False)

        # Subscribe to challenge topic
        challenge_topic = f"fse-01/{candidate_id}/challenge"
        client.subscribe(challenge_topic, qos=1)
        logger.info(f"Subscribed to topic: {challenge_topic}")
    else:
        logger.error(f"MQTT Connection failed with code {rc}")
        _worker_state["is_connected"] = False
        _worker_state["last_error"] = f"Connection error rc={rc}"


def _on_disconnect(client, userdata, rc, properties=None):
    logger.warning(f"MQTT Disconnected (rc={rc})")
    _worker_state["is_connected"] = False
    if rc != 0:
        _worker_state["last_error"] = f"Unexpected disconnect rc={rc}"


def _on_message(client, userdata, msg):
    candidate_id = userdata.get("candidate_id", "12")
    response_topic = f"fse-01/{candidate_id}/response"
    logger.info(f"MQTT Received message on topic: {msg.topic}")

    _worker_state["total_challenges_received"] += 1
    _worker_state["last_challenge_time"] = timezone.now().isoformat()

    try:
        payload_str = msg.payload.decode("utf-8")
        payload = json.loads(payload_str)
        challenge_id = payload.get("challenge_id", "UNKNOWN")
        _worker_state["last_challenge_id"] = challenge_id

        # Process challenge via MqttChallengeService
        response, resp_status = MqttChallengeService.handle_challenge(payload, candidate_id)
        _worker_state["last_response_status"] = resp_status

        # Publish response
        client.publish(response_topic, json.dumps(response), qos=1, retain=False)
        logger.info(f"Published response for challenge {challenge_id} with status {resp_status}")

    except Exception as e:
        logger.error(f"Error processing MQTT message: {e}", exc_info=True)
        _worker_state["last_error"] = str(e)
        _worker_state["last_response_status"] = "FAILED"
        try:
            err_resp = {
                "protocol_version": "1.0",
                "candidate_id": candidate_id,
                "challenge_id": "UNKNOWN",
                "status": "FAILED",
                "error_code": "INTERNAL_ERROR",
                "message": str(e),
                "processed_at": timezone.now().isoformat()
            }
            client.publish(response_topic, json.dumps(err_resp), qos=1, retain=False)
        except Exception:
            pass


def run_mqtt_worker():
    """Main function to run the MQTT worker loop."""
    global _client_instance, _heartbeat_thread
    broker_host = getattr(settings, 'MQTT_BROKER_HOST', '152.42.238.142')
    broker_port = getattr(settings, 'MQTT_BROKER_PORT', 1883)
    candidate_id = str(getattr(settings, 'MQTT_CANDIDATE_ID', '12'))
    keepalive = getattr(settings, 'MQTT_KEEPALIVE', 60)
    client_id = generate_client_id(candidate_id)

    _worker_state["broker_host"] = broker_host
    _worker_state["broker_port"] = broker_port
    _worker_state["candidate_id"] = candidate_id
    _worker_state["client_id"] = client_id

    # Initialize client (support paho-mqtt 2.x callback API)
    try:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            userdata={"candidate_id": candidate_id}
        )
    except AttributeError:
        client = mqtt.Client(
            client_id=client_id,
            userdata={"candidate_id": candidate_id}
        )

    _client_instance = client

    # Set Last Will & Testament (LWT)
    status_topic = f"fse-01/{candidate_id}/status"
    lwt_payload = {
        "status": "OFFLINE",
        "candidate_id": candidate_id,
        "timestamp": timezone.now().isoformat()
    }
    client.will_set(status_topic, json.dumps(lwt_payload), qos=1, retain=False)

    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message

    # Start Heartbeat thread
    _heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(client, candidate_id),
        daemon=True,
        name="MQTT-Heartbeat"
    )
    _heartbeat_thread.start()

    logger.info(f"Connecting to MQTT broker {broker_host}:{broker_port} as {client_id}...")

    # Connect with retry backoff
    while not _stop_event.is_set():
        try:
            client.connect(broker_host, broker_port, keepalive)
            client.loop_forever()
        except Exception as e:
            _worker_state["is_connected"] = False
            _worker_state["last_error"] = str(e)
            logger.warning(f"MQTT connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)


def start_mqtt_worker_background():
    """Starts the MQTT worker in a background daemon thread."""
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _stop_event.clear()
        _worker_thread = threading.Thread(
            target=run_mqtt_worker,
            daemon=True,
            name="MQTT-Worker"
        )
        _worker_thread.start()
        logger.info("MQTT worker background thread started.")
