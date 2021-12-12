from django.urls import path, re_path

from display import consumers

websocket_urlpatterns = [
    path('ws/tracks/global/', consumers.GlobalConsumer.as_asgi()),
    path('ws/traffic/airsports/', consumers.AirsportsPositionsConsumer.as_asgi()),
    re_path(r'ws/tracks/(?P<navigation_task>\w+)/$', consumers.TrackingConsumer.as_asgi()),
    re_path(r'ws/contestresults/(?P<contest_pk>\w+)/$', consumers.ContestResultsConsumer.as_asgi())
]
