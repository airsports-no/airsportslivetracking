from django.conf.urls import url
from django.urls import path
from django.views.generic import TemplateView, RedirectView

from display.views import frontend_view, RetrieveContestApi, import_track, frontend_view_offline, \
    get_data_from_time_for_contest, get_data_from_time_for_contestant, frontend_view_table, frontend_view_map

urlpatterns = [
    path('importtrack', import_track, name="import_track"),
    path('frontend/<int:pk>/table/', frontend_view_table, name="frontend_view_table"),
    path('frontend/<int:pk>/map/', frontend_view_map, name="frontend_view_map"),
    path('frontend/<int:pk>/', frontend_view, name="frontend_view"),
    # path('frontend/offline/<int:pk>/', frontend_view_offline, name="frontend_view_offline"),
    path('api/contest/detail/<int:pk>', RetrieveContestApi.as_view()),
    path('api/contest/track_data/<int:contest_pk>', get_data_from_time_for_contest),
    path('api/contestant/track_data/<int:contestant_pk>', get_data_from_time_for_contestant)
]
