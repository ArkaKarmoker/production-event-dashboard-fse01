"""URL configuration for core project - CSI Smart Tech FSE 01."""

from django.contrib import admin
from django.urls import path
from modules.events.views import EventsApiView
from modules.state.views import StateApiView
from modules.ack.views import AckApiView
from modules.mqtt_worker.views import MqttStatusApiView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Required 3 REST APIs (JSON)
    path('api/events', EventsApiView.as_view(), name='api-events'),
    path('api/events/', EventsApiView.as_view(), name='api-events-slash'),

    path('api/state', StateApiView.as_view(), name='api-state'),
    path('api/state/', StateApiView.as_view(), name='api-state-slash'),

    path('api/ack', AckApiView.as_view(), name='api-ack'),
    path('api/ack/', AckApiView.as_view(), name='api-ack-slash'),

    # MQTT Live Monitoring endpoint for dashboard
    path('api/mqtt/status', MqttStatusApiView.as_view(), name='api-mqtt-status'),
    path('api/mqtt/status/', MqttStatusApiView.as_view(), name='api-mqtt-status-slash'),
]
