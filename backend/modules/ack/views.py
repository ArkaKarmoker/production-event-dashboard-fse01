"""REST API view for POST /api/ack."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .service import AckService


class AckApiView(APIView):
    """
    POST /api/ack
    Body: { "event_ids": ["EV-101", "EV-102"] }
    Returns: [ { "event_id": str, "status": str } ]
    """

    def post(self, request, *args, **kwargs):
        payload = request.data

        if not isinstance(payload, dict) or "event_ids" not in payload:
            return Response(
                {"error": "Request body must be a JSON object containing 'event_ids' list."},
                status=status.HTTP_400_BAD_REQUEST
            )

        event_ids = payload.get("event_ids")
        if not isinstance(event_ids, list):
            return Response(
                {"error": "'event_ids' must be a list of strings."},
                status=status.HTTP_400_BAD_REQUEST
            )

        results = AckService.acknowledge_events(event_ids)
        return Response(results, status=status.HTTP_200_OK)
