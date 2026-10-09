"""URL configuration for core project - CSI Smart Tech FSE 01."""

from django.contrib import admin
from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.response import Response
from modules.events.views import EventsApiView
from modules.state.views import StateApiView
from modules.ack.views import AckApiView
from modules.mqtt_worker.views import MqttStatusApiView


@api_view(['GET'])
def api_root(request):
    """Root entrypoint displaying system metadata and available API links."""
    base_url = request.build_absolute_uri('/')[:-1]
    return Response({
        "system": "CSI Smart Tech Ltd | Production Event Processing & MQTT System",
        "assessment": "FSE 01 Practical Assessment",
        "candidate": "Arka Karmoker",
        "candidate_id": "12",
        "status": "ONLINE",
        "endpoints": {
            "events_ingestion": f"{base_url}/api/events",
            "state_summary": f"{base_url}/api/state?view=summary",
            "state_pending": f"{base_url}/api/state?view=pending",
            "state_exceptions": f"{base_url}/api/state?view=exceptions",
            "acknowledgement": f"{base_url}/api/ack",
            "mqtt_status": f"{base_url}/api/mqtt/status",
            "django_admin": f"{base_url}/admin/",
        }
    })


urlpatterns = [
    # Root Entrypoint
    path('', api_root, name='api-root'),

    # Django Admin
    path('admin/', admin.site.urls),

    # Required 3 REST APIs (JSON)
    path('api/events', EventsApiView.as_view(), name='api-events'),
    path('api/events/', EventsApiView.as_view(), name='api-events-slash'),

    path('api/state', StateApiView.as_view(), name='api-state'),
    path('api/state/', StateApiView.as_view(), name='api-state-slash'),
    path('api/stats', StateApiView.as_view(), name='api-stats-alias'),
    path('api/stats/', StateApiView.as_view(), name='api-stats-alias-slash'),

    path('api/ack', AckApiView.as_view(), name='api-ack'),
    path('api/ack/', AckApiView.as_view(), name='api-ack-slash'),

    # MQTT Live Monitoring endpoint for dashboard
    path('api/mqtt/status', MqttStatusApiView.as_view(), name='api-mqtt-status'),
    path('api/mqtt/status/', MqttStatusApiView.as_view(), name='api-mqtt-status-slash'),
]
