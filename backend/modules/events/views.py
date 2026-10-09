"""REST API view for POST /api/events."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .service import EventService


class EventsApiView(APIView):
    """
    POST /api/events
    Accepts a single event JSON object or a JSON array of event objects.
    Returns: { "results": [ { "event_id": str, "status": str, "message": str } ] }
    """

    def post(self, request, *args, **kwargs):
        payload = request.data

        # Top-level check: must be a dict or a list
        if not isinstance(payload, (dict, list)):
            return Response(
                {"error": "Top-level request must be a JSON object or array of objects."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Empty list is accepted and returns empty results
        if isinstance(payload, list) and len(payload) == 0:
            return Response({"results": []}, status=status.HTTP_200_OK)

        batch_result = EventService.process_batch(payload)
        return Response(batch_result, status=status.HTTP_200_OK)
