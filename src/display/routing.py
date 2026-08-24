from django.urls import path

from display import consumers

websocket_urlpatterns = [
    path("ws/traffic/airsports/", consumers.AirsportsPositionsConsumer.as_asgi()),
    path("ws/tracks/<int:navigation_task>/", consumers.TrackingConsumer.as_asgi()),
    path("ws/contestresults/<int:contest_pk>/", consumers.ContestResultsConsumer.as_asgi()),
]
