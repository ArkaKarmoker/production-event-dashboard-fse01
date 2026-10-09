"""Internal domain event callbacks for modular monolith boundaries."""

import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)

EVENT_ACCEPTED = "EVENT_ACCEPTED"
VOID_RESOLVED = "VOID_RESOLVED"
EVENT_ACKNOWLEDGED = "EVENT_ACKNOWLEDGED"

_subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {
    EVENT_ACCEPTED: [],
    VOID_RESOLVED: [],
    EVENT_ACKNOWLEDGED: [],
}

def subscribe(event_name: str, handler: Callable[[Dict[str, Any]], None]) -> None:
    if event_name in _subscribers:
        _subscribers[event_name].append(handler)

def emit(event_name: str, payload: Dict[str, Any]) -> None:
    handlers = _subscribers.get(event_name, [])
    for handler in handlers:
        try:
            handler(payload)
        except Exception as e:
            logger.error(f"Error executing callback for {event_name}: {e}")
