from django.urls import path, re_path

from display import consumers

websocket_urlpatterns = [
    re_path(r'ws/tracks/(?P<navigation_task>\w+)/$', consumers.TrackingConsumer.as_asgi())
]