from django.urls import path

from display.views import frontend_view, import_track, \
    get_data_from_time_for_contestant, frontend_view_table, frontend_view_map, \
    ImportFCNavigationTask

urlpatterns = [
    path('importtrack', import_track, name="import_track"),
    path('frontend/<int:pk>/table/', frontend_view_table, name="frontend_view_table"),
    path('frontend/<int:pk>/map/', frontend_view_map, name="frontend_view_map"),
    path('frontend/<int:pk>/', frontend_view, name="frontend_view"),
    path('api/contestant/track_data/<int:contestant_pk>', get_data_from_time_for_contestant),
]
