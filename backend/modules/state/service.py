"""State module service layer."""

from typing import Dict, Any, List, Optional
from .queries import StateQueries


class StateService:
    @staticmethod
    def get_summary(source_id: Optional[str] = None) -> Dict[str, int]:
        return StateQueries.get_summary(source_id=source_id)

    @staticmethod
    def get_pending(source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return StateQueries.get_pending(source_id=source_id)

    @staticmethod
    def get_exceptions(source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return StateQueries.get_exceptions(source_id=source_id)
