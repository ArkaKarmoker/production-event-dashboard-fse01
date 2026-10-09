"""REST API view for GET /api/state."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .service import StateService
from modules.shared.contracts import ALLOWED_VIEWS, VIEW_SUMMARY, VIEW_PENDING, VIEW_EXCEPTIONS


class StateApiView(APIView):
    """
    GET /api/state?source_id=LINE-01&view=summary
    Query params:
      - source_id: optional string
      - view: required ('summary', 'pending', or 'exceptions')
    """

    def get(self, request, *args, **kwargs):
        view_type = request.query_params.get("view")
        source_id = request.query_params.get("source_id") or None

        if not view_type or view_type not in ALLOWED_VIEWS:
            return Response(
                {
                    "error": f"Parameter 'view' is required and must be one of: {', '.join(ALLOWED_VIEWS)}."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if view_type == VIEW_SUMMARY:
            data = StateService.get_summary(source_id=source_id)
            return Response(data, status=status.HTTP_200_OK)

        elif view_type == VIEW_PENDING:
            data = StateService.get_pending(source_id=source_id)
            return Response(data, status=status.HTTP_200_OK)

        elif view_type == VIEW_EXCEPTIONS:
            data = StateService.get_exceptions(source_id=source_id)
            return Response(data, status=status.HTTP_200_OK)
