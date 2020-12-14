from django.urls import path

from display.views import frontend_view, import_route, frontend_view_table, frontend_view_map, \
    GetDataFromTimeForContestant, renew_token

urlpatterns = [
    path('importroute', import_route, name="import_route"),
    path('frontend/<int:pk>/table/', frontend_view_table, name="frontend_view_table"),
    path('frontend/<int:pk>/map/', frontend_view_map, name="frontend_view_map"),
    path('frontend/<int:pk>/', frontend_view, name="frontend_view"),
    path('api/contestant/track_data/<int:contestant_pk>', GetDataFromTimeForContestant.as_view(), name="trackdata"),
    path('token/renew', renew_token, name ="renewtoken")
]
