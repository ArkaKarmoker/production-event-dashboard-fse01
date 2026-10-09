"""API view to inspect MQTT worker live status."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .worker import get_worker_status


class MqttStatusApiView(APIView):
    """
    GET /api/mqtt/status
    Returns the live status of the MQTT worker client for frontend monitoring.
    """

    def get(self, request, *args, **kwargs):
        current_status = get_worker_status()
        return Response(current_status, status=status.HTTP_200_OK)
